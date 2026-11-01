from contextlib import chdir, closing, redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import pandas as pd
from openpyxl import load_workbook

from auto_analyse import analyze_file, build_report
from auto_analyse.cli import _discover_latest, main
from auto_analyse.config import load_config
from auto_analyse.io_utils import validate_outputs
from auto_analyse.report import header_note_specs
from auto_analyse.brand.cli import main as brand_main
from auto_analyse.brand.analysis import analyze_file as analyze_brand
from auto_analyse.brand.config import BrandConfig

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples/demo/retail.csv"
CONFIG = ROOT / "config/demo-retail.toml"


class CliSafetyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def rejects(self, args):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(args)
        self.assertEqual(error.exception.code, 2)

    def run_cli(self, args):
        capture = io.StringIO()
        with redirect_stderr(io.StringIO()), redirect_stdout(capture):
            self.assertEqual(main(args), 0)
        return json.loads(capture.getvalue())

    def test_inbox_always_wins_over_newer_example_and_ignores_lockfiles(self):
        inbox = self.root / "inbox"
        examples = self.root / "examples"
        inbox.mkdir()
        examples.mkdir()
        own = inbox / "customer.csv"
        own.write_text("synthetic")
        demo = examples / "demo.csv"
        demo.write_text("synthetic")
        (inbox / "~$locked.xlsx").write_text("lock")
        os.utime(own, (100, 100))
        os.utime(demo, (200, 200))
        self.assertEqual(_discover_latest([inbox, examples]), own)
        own.unlink()
        self.assertEqual(_discover_latest([inbox, examples]), demo)

    def test_missing_explicit_config_never_falls_back(self):
        self.rejects([str(DEMO), "--config", str(self.root / "missing.toml")])
        with self.assertRaises(FileNotFoundError):
            load_config(self.root / "missing.toml")
        invalid = self.root / "invalid.toml"
        invalid.write_text('[monitoring]\nprice_alert_threshold = -1\n')
        with self.assertRaises(ValueError):
            load_config(invalid)

    def test_source_xlsx_is_never_overwritten_even_with_override(self):
        source = self.root / "input.xlsx"
        pd.read_csv(DEMO, dtype={"product_id": str, "gtin": str}).to_excel(source, index=False)
        original = source.read_bytes()
        for extra in ([], ["--overwrite"]):
            self.rejects([str(source), "--config", str(CONFIG), "-o", str(source)] + extra)
            self.assertEqual(source.read_bytes(), original)

    def test_hardlink_and_sidecar_cannot_overwrite_source(self):
        source = self.root / "source.csv"
        source.write_text("synthetic")
        alias = self.root / "alias.xlsx"
        try:
            os.link(source, alias)
        except OSError:
            self.skipTest("Hardlinks are unavailable on this filesystem")
        with self.assertRaisesRegex(ValueError, "råfilen"):
            validate_outputs(source, [alias], overwrite=True)
        with self.assertRaisesRegex(ValueError, "råfilen"):
            validate_outputs(source, [self.root / "out.xlsx", source], overwrite=True)
        self.assertEqual(source.read_text(), "synthetic")

    def test_existing_sidecar_stops_before_any_report_is_written(self):
        out = self.root / "out.xlsx"
        sidecar = out.with_suffix(".json")
        sidecar.write_text("keep this synthetic sentinel")
        args = [str(DEMO), "--config", str(CONFIG), "-o", str(out)]
        self.rejects(args)
        self.assertFalse(out.exists())
        self.assertEqual(sidecar.read_text(), "keep this synthetic sentinel")
        result = self.run_cli(args + ["--overwrite"])
        self.assertTrue(Path(result["report"]).is_file())
        self.rejects(args)

    def test_demo_fallback_and_explicit_data_selection(self):
        for relative in ("examples/demo/retail.csv", "config/demo-retail.toml"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        with chdir(self.root):
            demo = self.run_cli([])
            self.assertTrue(demo["demo"])
            inbox = Path("data/inbox")
            inbox.mkdir(parents=True)
            shutil.copyfile(DEMO, inbox / "mine.csv")
            result = self.run_cli(["--config", str(CONFIG)])
            self.assertFalse(result["demo"])
            self.assertEqual(Path(result["input"]).name, "mine.csv")
            self.rejects([str(DEMO), "--demo"])

    def test_custom_labels_thresholds_and_raw_names_are_preserved(self):
        config = load_config(CONFIG)
        config = replace(config, retailer=replace(config.retailer, name="Testhandel"),
                         monitoring=replace(config.monitoring, price_alert_threshold=.07, critical_price_alert_threshold=.25, underpricing_threshold=-.08))
        frame = pd.read_csv(DEMO, dtype={"product_id": str, "gtin": str})
        frame.loc[frame.product_id.eq("000001"), "model"] = "Flisekompaniet nevnt i rånavnet"
        frame.loc[frame.product_id.eq("000008"), "model"] = '=HYPERLINK("https://example.com")'
        source = self.root / "custom.csv"
        frame.to_csv(source, index=False)
        result = analyze_file(source, config)
        output = build_report(result, config, self.root / "custom.xlsx")
        with closing(load_workbook(output)) as wb:
            self.assertEqual(wb["Konkurrenter"]["F1"].value, "Testhandel billigere")
            self.assertEqual(wb["Kategorier"]["I1"].value, "Andel >7 % over billigste")
            self.assertEqual(wb["Analyse & oppsummering"]["A8"].value, "PRISVARSLER >7 %")
            self.assertEqual(wb["Analyse & oppsummering"]["D9"].value, 1)
            self.assertIn("8 % under", wb["Analyse & oppsummering"]["A19"].value)
            values = [row[3] for row in wb["Prisvarsler"].iter_rows(min_row=2, max_col=14)]
            self.assertTrue(any(cell.value == "Flisekompaniet nevnt i rånavnet" for cell in values))
            self.assertTrue(any(str(cell.value).startswith("=HYPERLINK") and cell.data_type == "s" for cell in values))
            for spec in header_note_specs(config):
                cell = wb[spec["sheet"]][spec["cell"]]
                self.assertEqual(cell.value, spec["header"])
                self.assertEqual(cell.comment.text, spec["note"])

    def test_brand_demo_end_to_end_and_independent_expected_metrics(self):
        source = ROOT / "examples/demo/brands.csv"
        results = analyze_brand(source, BrandConfig(price_evidence_mode="synthetic"), allow_synthetic=True)
        self.assertEqual(len(results), 2)
        maker = next(r for r in results if r.summary["supplier"] == "demo-maker.example")
        self.assertEqual(maker.summary["products"], 4)
        self.assertEqual(maker.summary["comparable"], 1)
        self.assertAlmostEqual(maker.summary["stock_rate"], .75)
        self.assertAlmostEqual(maker.summary["median_gap"], .4)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(brand_main(["--demo", "--output-dir", str(self.root / "brand")]), 0)
        self.assertEqual(len(list((self.root / "brand").glob("*.xlsx"))), 2)

    def test_mixed_currency_rejected_and_missing_comparison_is_json_null(self):
        frame = pd.read_csv(DEMO, dtype={"product_id": str, "gtin": str})
        source = self.root / "input.csv"
        frame.loc[0, "currency"] = "EUR"
        frame.to_csv(source, index=False)
        self.rejects([str(source), "--config", str(CONFIG)])
        frame.loc[0, "currency"] = "NOK"
        frame.loc[frame.scraper_key.eq("demo_market"), "availability_status"] = "out_of_stock"
        frame.to_csv(source, index=False)
        paths = self.run_cli([str(source), "--config", str(CONFIG), "-o", str(self.root / "empty-comparison.xlsx")])
        manifest = json.loads(Path(paths["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["comparable_in_stock"], 0)
        self.assertIsNone(manifest["median_gap_to_cheapest"])
        with closing(load_workbook(paths["report"])) as wb:
            self.assertIn("Ikke beregnbart", wb["Analyse & oppsummering"]["A13"].value)


if __name__ == "__main__":
    unittest.main()
