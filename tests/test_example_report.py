from pathlib import Path
import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import load_workbook

from auto_analyse import analyze_file, build_report, load_config
from auto_analyse.cli import main
from auto_analyse.report import header_note_specs


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/demo/retail.csv"
CONFIG = ROOT / "config/demo-retail.toml"


class ExampleReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CONFIG)
        cls.analysis = analyze_file(EXAMPLE, cls.config)

    def test_example_metrics_match_reference(self):
        summary = self.analysis.summary
        self.assertEqual(summary["raw_rows"], 32)
        self.assertEqual(summary["target_products"], 8)
        self.assertEqual(summary["comparable_in_stock"], 5)
        self.assertEqual(summary["above_5pct_count"], 2)
        self.assertEqual(summary["above_15pct_count"], 2)
        self.assertEqual(summary["availability_risk_count"], 1)
        self.assertEqual(summary["underpricing_watch_count"], 1)
        self.assertAlmostEqual(summary["match_rate"], 7 / 8)
        self.assertAlmostEqual(summary["price_leader_share"], 2 / 5)
        self.assertAlmostEqual(summary["median_gap_to_cheapest"], .04)
        self.assertEqual(summary["own_price_changed_products"], 1)
        self.assertEqual(summary["competitor_best_price_changed_products"], 1)

    def test_report_contract_and_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            output = build_report(
                self.analysis, self.config, Path(directory) / "report.xlsx"
            )
            wb = load_workbook(output, data_only=False)
        self.assertEqual(
            wb.sheetnames,
            [
                "Kategorier",
                "Konkurrenter",
                "Prisvarsler",
                "Tilgjengelighetsrisiko",
                "Marginvakt",
                "Analyse & oppsummering",
                "Kolonneforklaringer",
            ],
        )
        self.assertEqual(
            [cell.value for cell in wb["Kategorier"][1]],
            [
                "Produktkategori",
                "Produkter",
                "Matchede produkter",
                "Matchgrad",
                "Sammenlignbare in-stock",
                "Egen lagerandel",
                "Konkurrent lagerdekning",
                "Prislederandel",
                "Andel >5 % over billigste",
                "Andel >15 % over billigste",
                "Median gap til billigste",
                "Prisvarsler",
                "Tilgjengelighetsrisiko",
            ],
        )
        self.assertEqual(
            [cell.value for cell in wb["Konkurrenter"][1]],
            [
                "Konkurrentdomene",
                "Matchede produkter",
                "In-stock-matcher",
                "Sammenlignbare in-stock",
                "Konkurrent billigere",
                "Demobutikken billigere",
                "Median konkurrentgap",
            ],
        )
        dashboard = wb["Analyse & oppsummering"]
        self.assertEqual(dashboard["A5"].value, 8)
        self.assertAlmostEqual(dashboard["D5"].value, 7 / 8)
        self.assertEqual(dashboard["A9"].value, 2)
        self.assertEqual(dashboard["J9"].value, 1)
        self.assertEqual(dashboard["D5"].number_format, "0%")
        self.assertTrue(all(not ws._charts for ws in wb.worksheets))
        self.assertEqual(wb["Kolonneforklaringer"].max_row, 63)
        expected_notes = header_note_specs(self.config)
        self.assertEqual(len(expected_notes), 68)
        for spec in expected_notes:
            cell = wb[spec["sheet"]][spec["cell"]]
            self.assertEqual(cell.value, spec["header"])
            self.assertIsNotNone(cell.comment)
            self.assertEqual(cell.comment.text, spec["note"])
        glossary = {
            (sheet, header): definition
            for sheet, header, definition in wb["Kolonneforklaringer"].iter_rows(min_row=2, values_only=True)
        }
        for (sheet, header), definition in glossary.items():
            cell = next(c for c in wb[sheet][1] if c.value == header)
            self.assertEqual(cell.comment.text, definition)
        self.assertEqual(sum(c.comment is not None for ws in wb for row in ws for c in row), 68)
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        self.assertNotIn("#REF!", cell.value)

    def test_cli_exports_notes_matching_workbook(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.xlsx"
            captured = io.StringIO()
            with patch("auto_analyse.cli.analyze_file", return_value=self.analysis), contextlib.redirect_stdout(captured):
                self.assertEqual(main([str(EXAMPLE), "--config", str(CONFIG), "-o", str(output)]), 0)
            paths = json.loads(captured.getvalue())
            manifest = json.loads(Path(paths["header_notes"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], 1)
            self.assertEqual(len(manifest["notes"]), 68)
            wb = load_workbook(output)
            for spec in manifest["notes"]:
                cell = wb[spec["sheet"]][spec["cell"]]
                self.assertEqual(cell.value, spec["header"])
                self.assertEqual(cell.comment.text, spec["note"])
            wb.close()


if __name__ == "__main__":
    unittest.main()
