from pathlib import Path
import tempfile
import unittest

from openpyxl import load_workbook

from auto_analyse import analyze_file, build_report, load_config


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/raw/flisekompaniet_category_extract_last_7_days_2026-08-20.zip"
CONFIG = ROOT / "config/report.toml"


class ExampleReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CONFIG)
        cls.analysis = analyze_file(EXAMPLE, cls.config)

    def test_example_metrics_match_reference(self):
        summary = self.analysis.summary
        self.assertEqual(summary["raw_rows"], 107_898)
        self.assertEqual(summary["target_products"], 4_063)
        self.assertEqual(summary["comparable_in_stock"], 1_467)
        self.assertEqual(summary["above_5pct_count"], 942)
        self.assertEqual(summary["above_15pct_count"], 754)
        self.assertEqual(summary["availability_risk_count"], 1_457)
        self.assertEqual(summary["underpricing_watch_count"], 70)
        self.assertAlmostEqual(summary["match_rate"], 0.7368939207482156)
        self.assertAlmostEqual(summary["price_leader_share"], 0.3231083844580777)
        self.assertAlmostEqual(summary["median_gap_to_cheapest"], 0.1852166525063721)

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
                "Flisekompaniet billigere",
                "Median konkurrentgap",
            ],
        )
        dashboard = wb["Analyse & oppsummering"]
        self.assertEqual(dashboard["A5"].value, 4_063)
        self.assertAlmostEqual(dashboard["D5"].value, 0.7368939207482156)
        self.assertEqual(dashboard["A9"].value, 942)
        self.assertEqual(dashboard["J9"].value, 1_457)
        self.assertEqual(dashboard["D5"].number_format, "0%")
        self.assertTrue(all(not ws._charts for ws in wb.worksheets))
        self.assertEqual(wb["Kolonneforklaringer"].max_row, 63)
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        self.assertNotIn("#REF!", cell.value)


if __name__ == "__main__":
    unittest.main()
