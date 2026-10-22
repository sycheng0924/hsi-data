import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import hsidata  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="latin-1")


class ParseSheetTest(unittest.TestCase):
    def test_full_day(self):
        row = hsidata.parse_sheet(fixture("d261021e.htm"))
        self.assertEqual(row, {
            "date": "2026-10-21",
            "close": 23651.87,
            "prevClose": 23867.74,
            "turnover": 176597304443,
            "halfDay": 0,
        })

    def test_half_day_has_no_afternoon_close(self):
        row = hsidata.parse_sheet(fixture("halfday_synthetic.htm"))
        self.assertEqual(row["date"], "2026-12-24")
        self.assertEqual(row["close"], 23651.87)
        self.assertEqual(row["prevClose"], 23867.74)
        self.assertEqual(row["halfDay"], 1)

    def test_unrelated_page(self):
        self.assertIsNone(hsidata.parse_sheet("<html>Page not found</html>"))


class ParseArchiveTest(unittest.TestCase):
    def test_rows_and_half_day_flag(self):
        out = hsidata.parse_archive(fixture("archive_sample.json"))
        self.assertEqual(out, {
            "2025-12-23": (150000000000, 0),
            "2025-12-24": (92524183098, 1),
        })


class ParseEastmoneyTest(unittest.TestCase):
    def test_dates_and_closes(self):
        out = hsidata.parse_eastmoney(fixture("eastmoney_sample.json"))
        self.assertEqual(out, {"2026-10-20": 23867.74, "2026-10-21": 23651.87})


class SaveTest(unittest.TestCase):
    def test_sorted_and_unchanged_rows_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hsi.json"
            rows = {
                "2026-10-21": {"date": "2026-10-21", "close": 2.0, "prevClose": 1.0, "turnover": 5, "halfDay": 0},
                "2026-10-20": {"date": "2026-10-20", "close": 1.0, "prevClose": 0.5, "turnover": 4, "halfDay": 0},
            }
            with mock.patch.object(hsidata, "DATA_FILE", path):
                self.assertTrue(hsidata.save(rows))
                self.assertFalse(hsidata.save(rows))
                doc = json.loads(path.read_text())
                self.assertEqual([r[0] for r in doc["rows"]], ["2026-10-20", "2026-10-21"])
                self.assertEqual(hsidata.load(), rows)


if __name__ == "__main__":
    unittest.main()
