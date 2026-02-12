import sys
import unittest
from pathlib import Path

# Allow importing scripts as modules
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import vnext_build_citations as vbc


class TestCitationsUnit(unittest.TestCase):
    def test_space_header_tsv(self):
        path = ROOT / "tests/fixtures/revised_ed/beck.tsv"
        config = vbc.SOURCE_CONFIGS["beck.tsv"]
        rows = list(vbc.read_tsv_rows(path, config))
        self.assertEqual(len(rows), 2)
        row, row_num = rows[0]
        self.assertIn("beck_id", row)
        self.assertEqual(row["beck_id"], "DMM1001")
        self.assertEqual(row_num, 2)

    def test_no_header_tsv(self):
        path = ROOT / "tests/fixtures/revised_ed/wellmann.tsv"
        config = vbc.SOURCE_CONFIGS["wellmann.tsv"]
        rows = list(vbc.read_tsv_rows(path, config))
        self.assertEqual(len(rows), 2)
        row, row_num = rows[0]
        self.assertEqual(row.get("book_num"), "1")
        self.assertEqual(row.get("chapter_num"), "1")
        self.assertEqual(row_num, 1)

    def test_roman_parsing(self):
        self.assertEqual(vbc.parse_roman("IIII"), 4)
        self.assertEqual(vbc.parse_roman("Cap. IV"), 4)
        self.assertEqual(vbc.parse_roman("Chap. II"), 2)
        self.assertIsNone(vbc.parse_roman("Textus primi"))

    def test_page_label_sort_key(self):
        self.assertLess(vbc.page_label_sort_key("12"), vbc.page_label_sort_key("12v"))
        self.assertLess(vbc.page_label_sort_key("1r"), vbc.page_label_sort_key("1v"))
        self.assertLess(vbc.page_label_sort_key("2"), vbc.page_label_sort_key("10"))

    def test_citation_ref_collisions(self):
        rows = [
            {"edition_id": "wellmann", "citation_ref": "b1|c1", "source_row": "1", "extra_json": ""},
            {"edition_id": "wellmann", "citation_ref": "b1|c1", "source_row": "2", "extra_json": ""},
        ]
        vbc.resolve_citation_ref_collisions(rows)
        refs = sorted(r["citation_ref"] for r in rows)
        self.assertEqual(refs, ["b1|c1-r1", "b1|c1-r2"])
        for row in rows:
            self.assertIn("citation_ref_collision", row.get("extra_json", ""))


if __name__ == "__main__":
    unittest.main()
