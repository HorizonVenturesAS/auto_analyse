from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook

from auto_analyse import analyze_file, load_config
from auto_analyse.analysis import REQUIRED_COLUMNS, _read_source


class ExcelInputTest(unittest.TestCase):
    def _save(self, directory, *, summary=True, duplicate=False, complete=True):
        workbook = Workbook()
        workbook.remove(workbook.active)
        if summary:
            workbook.create_sheet("Summary").append(["Report", "Value"])
            workbook.create_sheet("Category mapping").append(["Category", "Status"])
        headers = sorted(REQUIRED_COLUMNS if complete else REQUIRED_COLUMNS - {"price"})
        for name in (["Raw observations", "Other raw data"] if duplicate else ["Raw observations"]):
            sheet = workbook.create_sheet(name)
            sheet.append(headers)
            sheet.append([{"product_id": "000123", "gtin": "0001234567890", "price": 99}.get(c, "example") for c in headers])
        path = Path(directory) / "source.xlsx"
        workbook.save(path)
        workbook.close()
        return path

    def test_finds_raw_sheet_after_summary_and_preserves_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._save(directory)
            original = path.read_bytes()
            frame = _read_source(path)
            self.assertEqual(set(frame.columns), REQUIRED_COLUMNS)
            self.assertEqual(len(frame), 1)
            self.assertEqual(frame.loc[0, "product_id"], "000123")
            self.assertEqual(frame.loc[0, "gtin"], "0001234567890")
            self.assertEqual(frame.loc[0, "price"], 99)
            self.assertEqual(path.read_bytes(), original)

    def test_single_data_sheet_still_works(self):
        with tempfile.TemporaryDirectory() as directory:
            frame = _read_source(self._save(directory, summary=False))
            self.assertEqual(frame.loc[0, "product_id"], "000123")

    def test_rejects_ambiguous_data_sheets(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Flere Excel-faner.*Raw observations, Other raw data"):
                _read_source(self._save(directory, duplicate=True))

    def test_missing_column_diagnostic_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            config = load_config(Path(__file__).resolve().parents[1] / "config/report.toml")
            with self.assertRaisesRegex(ValueError, "Råfilen mangler obligatoriske kolonner: price$"):
                analyze_file(self._save(directory, summary=False, complete=False), config)
