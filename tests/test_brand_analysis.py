import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from openpyxl import Workbook, load_workbook

from auto_analyse.brand import BrandConfig, analyze_file, build_report
from auto_analyse.brand.analysis import NA, read_source
from auto_analyse.brand.cli import discover_latest, main
from auto_analyse.brand.config import load_config
from auto_analyse.brand.report import COLUMNS, KPI_KEYS, SHEETS, header_note_specs


def offer(product="p1", shop="a.no", price=100, **overrides):
    return {
        "supplier": "https://www.supplier.no/products", "requested_brand": "Brand A",
        "brand": "Brand A", "product_id": product, "title": "Produkt " + product,
        "category": "Kategori", "gtin": "000" + product,
        "retailer": shop, "offer_id": product + "-" + shop, "price": price,
        "currency": "NOK", "availability": "in_stock", "observed_at": "2026-09-14T12:00:00Z",
        "is_used": False, "is_stale": False, "regular_price": None,
        "shipping": None, "price_qualifier": "", "size": "", "color": "",
        "offer_title": "Produkt " + product,
        "prisradar_url": "https://prisradar.no/produkter/" + product, "retailer_url": "",
        **overrides,
    }


def fixture():
    return [
        offer(), offer(price=110, offer_id="higher-offer", regular_price=200),
        offer(shop="B.no", price=120, regular_price=150), offer(shop="https://www.c.no/path", price=140),
        offer("p2", price=200), offer("p2", "b.no", 250),
        offer("p3", price=300),
        offer("p4", "", None, offer_id="", availability="", is_used=None, is_stale=None),
        offer("p5", price=100), offer("p5", "b.no", 600),
        offer("other", supplier="supplier-two.no", requested_brand="Brand B", brand="Brand B"),
    ]


class BrandAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, rows, name="input.csv"):
        path = self.root / name
        pd.DataFrame(rows).to_csv(path, index=False)
        return path

    def analyze(self, rows=None, config=None):
        return analyze_file(self.source(rows if rows is not None else fixture()), config, supplier="supplier.no")[0]

    def test_price_math_dedup_peers_and_supplier_isolation(self):
        source = self.source(fixture())
        original = source.read_bytes()
        results = analyze_file(source)
        self.assertEqual(len(results), 2)
        r = next(r for r in results if r.summary["supplier"] == "supplier.no")
        s = r.summary
        self.assertEqual((s["products"], s["stores"], s["with_offers"], s["comparable"]), (5, 3, 4, 2))
        self.assertEqual((s["single_stock"], s["no_stock"], s["review_products"]), (1, 1, 1))
        self.assertAlmostEqual(s["stock_rate"], .8)
        self.assertAlmostEqual(s["median_gap"], .325)
        p = r.products.set_index("product_id")
        self.assertEqual(p.loc["p1", "price_stores"], 3)
        self.assertEqual(p.loc["p1", "median_price"], 120)
        self.assertEqual(p.loc["p1", "gap_nok"], 40)
        self.assertEqual(p.loc["p5", "status"], "Til kontroll")
        self.assertTrue(pd.isna(p.loc["p5", "gap_pct"]))
        shops = r.retailers.set_index("retailer")
        self.assertEqual(shops.loc["a.no", "peer_products"], 1)
        self.assertAlmostEqual(shops.loc["a.no", "peer_gap"], 100 / 130 - 1)
        self.assertEqual(shops.loc["a.no", "price_products"], 2)
        self.assertEqual(shops.loc["a.no", "leader_share"], 1)
        self.assertEqual(shops.loc["a.no", "campaigns"], 0)
        self.assertEqual(len(r.campaigns), 1)
        self.assertAlmostEqual(r.campaigns.iloc[0].discount, .2)
        self.assertEqual(r.observations.audit_selected_store_offer.sum(), 8)
        self.assertEqual(r.observations.audit_price_eligible.sum(), 6)
        self.assertIn("Annet tilbud valgt", r.observations.loc[r.observations.offer_id.eq("higher-offer"), "audit_price_exclusion"].iloc[0])
        self.assertEqual(set(r.observations.supplier_key), {"supplier.no"})
        self.assertEqual(source.read_bytes(), original)

    def test_latest_product_snapshot_never_reuses_old_store(self):
        rows = [offer(), offer(shop="b.no", price=80), offer(price=150, observed_at="2026-09-15T12:00:00Z")]
        r = self.analyze(rows)
        self.assertEqual(r.summary["comparable"], 0)
        self.assertEqual(r.products.iloc[0].offer_stores, 1)
        self.assertEqual(r.products.iloc[0].min_price, 150)
        self.assertEqual((r.observations.audit_price_exclusion == "Eldre snapshot").sum(), 2)

    def test_price_eligibility_does_not_rewrite_observed_availability(self):
        rows = [offer(), offer(shop="b.no", currency="EUR"), offer(shop="c.no", is_used=True),
                offer(shop="d.no", is_stale=True), offer(shop="e.no", is_used="unknown"),
                offer(shop="f.no", price=-1), offer(shop="g.no", price=float("inf")),
                offer(shop="h.no", availability="preorder"), offer(shop="i.no", price_qualifier="club")]
        r = self.analyze(rows)
        self.assertEqual(r.products.iloc[0].price_stores, 1)
        self.assertEqual(r.products.iloc[0].stock_stores, 8)
        self.assertEqual(r.summary["comparable"], 0)
        self.assertIn("Ugyldig pris", " ".join(r.observations.audit_price_exclusion))

    def test_variant_conflict_and_gtin_reuse_quarantine_whole_product(self):
        rows = [offer(title="Sko - 38.5", offer_title="Sko, 38 1/2 EU", size="38.5"),
                offer(shop="b.no", title="Sko - 38.5", offer_title="Sko, 39 1/2 EU", size="38.5"),
                offer("p2", gtin="001234"), offer("p3", gtin="001234")]
        r = self.analyze(rows)
        p = r.products.set_index("product_id")
        self.assertIn("størrelsesavvik", p.loc["p1", "review"])
        self.assertEqual(p.loc["p1", "size"], "38.5")
        self.assertIn("GTIN", p.loc["p2", "review"])
        self.assertIn("GTIN", p.loc["p3", "review"])
        self.assertEqual(r.summary["review_products"], 3)
        self.assertEqual(r.summary["comparable"], 0)

    def test_brand_alias_and_case_normalization(self):
        rows = [offer(requested_brand="JRG", brand="Jrg Sanipex"),
                offer(shop="b.no", price=200, requested_brand="jrg", brand="Jrg Sanipex")]
        r = self.analyze(rows)
        self.assertEqual(r.summary["comparable"], 1)
        self.assertEqual(r.summary["brands"], 1)
        bad = self.analyze([offer(brand="Unrelated"), offer(shop="b.no")])
        self.assertIn("Brandnavn", bad.products.iloc[0].review)

    def test_exact_duplicates_and_conflicting_offer_ids(self):
        r = self.analyze([offer(), offer(), offer(shop="b.no", price=150)])
        self.assertEqual(r.summary["comparable"], 1)
        self.assertEqual(r.summary["selected_rows"], 2)
        self.assertEqual(r.observations.audit_exact_duplicate.sum(), 1)
        bad = self.analyze([offer(), offer(price=120)])
        self.assertIn("tilbuds-ID", bad.products.iloc[0].review)

    def test_stock_gaps_and_empty_price_ground(self):
        r = self.analyze([offer(availability="out_of_stock"), offer(shop="b.no", availability="backorder"),
                          offer(shop="c.no"), offer("p2", "", None, offer_id="", availability="")])
        issues = r.availability.issue.value_counts()
        self.assertEqual(issues["Butikken mangler lager; andre har varen"], 2)
        self.assertEqual(issues["Kun én butikk på lager"], 1)
        self.assertEqual(issues["Ingen aktive tilbud"], 1)
        self.assertIsNone(r.summary["median_gap"])
        self.assertTrue(r.retailers.peer_gap.isna().all())

    def test_no_offer_supplier_can_still_render(self):
        r = self.analyze([offer(shop="", price=None, offer_id="", availability="")])
        self.assertEqual(r.summary["stores"], 0)
        path = build_report(r, BrandConfig(), self.root / "empty.xlsx")
        with contextlib.closing(load_workbook(path)) as wb:
            self.assertEqual(wb["Analyse & oppsummering"]["D10"].value, NA)
            self.assertEqual(wb["Nettbutikker"]["A3"].value, "Ingen rader i denne kategorien.")

    def test_snapshot_age_unknown_flags_and_invalid_timestamps(self):
        r = self.analyze([offer(), offer(shop="b.no"), offer("new", observed_at="2026-09-20T12:00:00Z")])
        self.assertIn("gammelt snapshot", r.products.set_index("product_id").loc["p1", "review"])
        unknown = self.analyze([offer(is_stale="nonsense")])
        self.assertEqual(unknown.products.iloc[0].price_stores, 0)
        for value in ("bad", "2026-09-14T12:00:00"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.analyze([offer(observed_at=value)])

    def test_freshness_reference_is_global_and_independent_of_supplier_filter(self):
        source = self.source([offer(), offer(shop="b.no"),
                              offer("other", supplier="other.no", observed_at="2026-09-20T12:00:00Z")])
        all_results = analyze_file(source)
        filtered = analyze_file(source, supplier="supplier.no")[0]
        unfiltered = next(r for r in all_results if r.summary["supplier"] == "supplier.no")
        self.assertEqual(filtered.summary["comparable"], 0)
        self.assertEqual(filtered.summary["snapshot_reference_time"], unfiltered.summary["snapshot_reference_time"])

    def test_configuration_file_matches_portable_defaults(self):
        config_path = Path(__file__).resolve().parents[1] / "config/brand.toml"
        self.assertEqual(load_config(config_path), BrandConfig())

    def test_equal_prices_and_tolerance_include_ties(self):
        r = self.analyze([offer(), offer(shop="b.no", price=100), offer(shop="c.no", price=101)])
        self.assertEqual(r.summary["comparable"], 1)
        self.assertTrue(r.retailers.leader_share.eq(1).all())
        self.assertAlmostEqual(r.summary["median_gap"], .01)

    def test_workbook_contract_notes_kpis_and_safe_text(self):
        rows = fixture()
        rows[0]["title"] = '=HYPERLINK("https://example.com")'
        # Keep same metadata across offers so this product remains comparable.
        for row in rows:
            if row["product_id"] == "p1":
                row["title"] = rows[0]["title"]
        r = self.analyze(rows)
        path = build_report(r, BrandConfig(), self.root / "report.xlsx")
        with contextlib.closing(load_workbook(path)) as wb:
            self.assertEqual(wb.sheetnames, list(SHEETS) + ["Analyse & oppsummering", "Kolonneforklaringer"])
            self.assertEqual(wb.active.title, "Analyse & oppsummering")
            for name, (_, keys) in SHEETS.items():
                self.assertEqual([c.value for c in wb[name][1]], [COLUMNS[k][0] for k in keys])
                self.assertIsNotNone(wb[name].auto_filter.ref)
            self.assertEqual(wb["Prisgap"]["C2"].number_format, "@")
            self.assertEqual(wb["Prisgap"]["C2"].data_type, "s")
            dashboard = wb["Analyse & oppsummering"]
            for key, cell in zip(KPI_KEYS, ["A6", "D6", "G6", "J6", "A10", "D10", "G10", "J10"]):
                expected = r.summary[key]
                self.assertAlmostEqual(dashboard[cell].value, expected)
            for spec in header_note_specs():
                cell = wb[spec["sheet"]][spec["cell"]]
                self.assertEqual(cell.value, spec["header"])
                self.assertEqual(cell.comment.text, spec["note"])
            glossary = {(s, h): definition for s, h, definition in wb["Kolonneforklaringer"].iter_rows(min_row=2, values_only=True)}
            for name, (_, keys) in SHEETS.items():
                for col, key in enumerate(keys, 1):
                    self.assertEqual(wb[name].cell(1, col).comment.text, glossary[(name, COLUMNS[key][0])])
            self.assertTrue(all(not ws._charts for ws in wb))
            seen_source = False
            for ws in wb:
                for row in ws:
                    for cell in row:
                        self.assertNotEqual(cell.data_type, "f")
                        self.assertNotEqual(cell.data_type, "e")
                        if cell.value == rows[0]["title"]:
                            seen_source = True
                            self.assertEqual(cell.data_type, "s")
            self.assertTrue(seen_source)

    def test_cli_exports_per_supplier_and_refuses_implicit_overwrite(self):
        source = self.source(fixture())
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        output = self.root / "out"
        capture = io.StringIO()
        args = [str(source), "--output-dir", str(output)]
        with contextlib.redirect_stdout(capture):
            self.assertEqual(main(args), 0)
        exports = json.loads(capture.getvalue())["reports"]
        self.assertEqual(len(exports), 2)
        for entry in exports:
            manifest = json.loads(Path(entry["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_sha256"], source_hash)
            self.assertEqual(manifest["report_type"], "brand")
            audit = pd.read_json(entry["observations"], lines=True)
            self.assertEqual(set(audit.supplier_key), {entry["supplier"]})
            notes = json.loads(Path(entry["header_notes"]).read_text(encoding="utf-8"))["notes"]
            self.assertEqual(notes, header_note_specs())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(args)
        self.assertEqual(error.exception.code, 2)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(args + ["--overwrite"]), 0)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)

    def test_input_validation_xlsx_sheet_selection_and_text_ids(self):
        wb = Workbook()
        wb.active.title = "Summary"
        wb.active.append(["Summary"])
        ws = wb.create_sheet("Raw")
        row = offer(product="000123", gtin="0000012345678")
        ws.append(list(row))
        ws.append(list(row.values()))
        path = self.root / "source.xlsx"
        wb.save(path)
        frame = read_source(path)
        self.assertEqual(frame.product_id.iloc[0], "000123")
        self.assertEqual(frame.gtin.iloc[0], "0000012345678")
        wb.copy_worksheet(ws)
        wb.save(path)
        wb.close()
        with self.assertRaisesRegex(ValueError, "Flere Excel-faner"):
            read_source(path)
        with self.assertRaisesRegex(ValueError, "Mangler obligatoriske"):
            read_source(self.source([{"price": 1}]))
        with self.assertRaisesRegex(ValueError, "supplier mangler"):
            self.analyze([offer(supplier="")])

    def test_config_and_discovery_are_separate_from_retail(self):
        with self.assertRaises(FileNotFoundError):
            load_config(self.root / "missing.toml")
        for kw in ({"extreme_price_ratio": 1}, {"min_peer_stores": 1}, {"price_leader_tolerance": -1}, {"max_snapshot_age_hours": float("nan")}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                BrandConfig(**kw)
        inbox = self.root / "data/inbox"
        inbox.mkdir(parents=True)
        (inbox / "retail.csv").write_text("retail")
        with self.assertRaisesRegex(ValueError, "brandråfil"):
            discover_latest(inbox / "brands")
        brands = inbox / "brands"
        brands.mkdir()
        (brands / "catalogue.csv").write_text("brand")
        self.assertEqual(discover_latest(brands).name, "catalogue.csv")
        # Existing non-recursive retail discovery cannot select brand files.
        from auto_analyse.cli import _discover_latest
        self.assertEqual(_discover_latest([inbox]).name, "retail.csv")


if __name__ == "__main__":
    unittest.main()
