import io
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject

from invoice_tool.errors import UserError
from invoice_tool.matching import match_invoices
from invoice_tool.models import InvoiceRow
from invoice_tool.parsing import normalize_ticket, parse_filename, read_workbook
from invoice_tool.pdf_service import clean_xref_references, csv_cell, inspect_pdf, safe_filename

from .fixtures import pdf_bytes, workbook_bytes


class RuleTests(unittest.TestCase):
    def test_cleanup_preserves_real_form_fields(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=300)
        bad = DictionaryObject({NameObject("/Type"): NameObject("/XRef")})
        valid = DictionaryObject(
            {
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/T"): TextStringObject("keep"),
            }
        )
        page[NameObject("/Annots")] = ArrayObject([bad, valid])
        writer.root_object[NameObject("/AcroForm")] = DictionaryObject(
            {NameObject("/Fields"): ArrayObject([bad, valid])}
        )
        buffer = io.BytesIO()
        writer.write(buffer)
        writer.close()
        reader = PdfReader(buffer)
        self.assertEqual(clean_xref_references(reader), 2)
        self.assertEqual(len(reader.pages[0]["/Annots"]), 1)
        self.assertEqual(reader.trailer["/Root"]["/AcroForm"]["/Fields"][0]["/T"], "keep")

    def test_ticket_full_length(self):
        self.assertEqual(normalize_ticket("784-1234567801"), "7841234567801")
        self.assertEqual(normalize_ticket("001-0234567801"), "0010234567801")
        self.assertEqual(normalize_ticket("1234567801"), "")
        self.assertEqual(normalize_ticket("784x1234567801"), "")

    def test_filename_separators(self):
        for name in [
            "示例甲784-1234567801.pdf",
            "示例甲-7841234567801.pdf",
            "示例甲_784_1234567801.pdf",
        ]:
            self.assertEqual(parse_filename(name), ("示例甲", "7841234567801"))

    def test_distinct_prefixes(self):
        self.assertNotEqual(normalize_ticket("784-1234567801"), normalize_ticket("999-1234567801"))

    def test_mismatch_is_not_fuzzy(self):
        rows = [InvoiceRow(2, "测试乙", "7841234567801", "A")]
        result = match_invoices(
            rows, [{"id": "f", "name": "测试甲-784-1234567801.pdf", "pages": 1}], [], {}
        )
        self.assertEqual(result["summary"]["matched"], 0)
        self.assertEqual(result["summary"]["unmatched_files"], 1)

    def test_duplicate_and_conflicting_rows_block(self):
        for project in ["A", "B"]:
            rows = [
                InvoiceRow(2, "甲", "7841234567801", "A"),
                InvoiceRow(3, "甲", "7841234567801", project),
            ]
            result = match_invoices(
                rows, [{"id": "f", "name": "甲-784-1234567801.pdf", "pages": 1}], [], {}
            )
            self.assertEqual(result["summary"]["blocked_rows"], 2)
            self.assertEqual(result["summary"]["ready_groups"], 0)

    def test_duplicate_files_block(self):
        files = [{"id": str(i), "name": "甲-784-1234567801.pdf", "pages": 1} for i in range(2)]
        result = match_invoices([InvoiceRow(2, "甲", "7841234567801", "A")], files, [], {})
        self.assertEqual(result["summary"]["ready_groups"], 0)

    def test_group_with_missing_file_not_exportable(self):
        rows = [
            InvoiceRow(2, "甲", "7841234567801", "A"),
            InvoiceRow(3, "乙", "9991234567801", "A"),
        ]
        result = match_invoices(
            rows, [{"id": "f", "name": "甲-784-1234567801.pdf", "pages": 2}], [], {}
        )
        self.assertEqual(result["summary"]["matched"], 1)
        self.assertTrue(result["groups"][0]["blocked"])

    def test_workbook_trim_and_extra_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.xlsx"
            path.write_bytes(workbook_bytes([["784-1234567801", "甲", " A ", "其他"]]))
            rows, issues, info = read_workbook(path)
            self.assertEqual(rows[0].project, "A")
            self.assertEqual(info["columns"]["name"], 2)
            self.assertEqual(len(issues), 1)

    def test_formulas_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.xlsx"
            path.write_bytes(workbook_bytes([["784-1234567801", "甲", "=1+1", "其他"]]))
            rows, _, _ = read_workbook(path)
            self.assertIn("公式", rows[0].error)

    def test_bad_workbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.xlsx"
            path.write_bytes(b"not a zip")
            with self.assertRaises(UserError):
                read_workbook(path)

    def test_pdf_invalid_encrypted_and_multipage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.pdf"
            path.write_bytes(b"not PDF")
            self.assertIn("error", inspect_pdf(path))
            path.write_bytes(pdf_bytes(encrypted=True))
            self.assertIn("加密", inspect_pdf(path)["error"])
            path.write_bytes(pdf_bytes(2))
            self.assertEqual(inspect_pdf(path)["pages"], 2)

    def test_safe_export_names_and_csv(self):
        self.assertNotIn("/", safe_filename("../A:B", "g001"))
        self.assertNotEqual(safe_filename("A/B", "g001"), safe_filename("A:B", "g002"))
        self.assertTrue(csv_cell('=HYPERLINK("bad")').startswith("'"))
        self.assertEqual(csv_cell("001234"), "001234")
