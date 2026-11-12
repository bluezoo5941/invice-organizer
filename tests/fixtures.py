"""Synthetic fixtures only; never write to an existing user workbook."""

import io

from openpyxl import Workbook
from pypdf import PdfWriter


def workbook_bytes(rows=None):
    book = Workbook()
    sheet = book.active
    sheet.append(["票号", "乘机人姓名", "项目名称", "其他字段"])
    for row in rows if rows is not None else [["784-1234567801", "测试甲", "项目A", "保留"]]:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def pdf_bytes(pages=1, encrypted=False):
    output = io.BytesIO()
    writer = PdfWriter()
    for i in range(pages):
        writer.add_blank_page(width=300 + i * 10, height=400)
    if encrypted:
        writer.encrypt("test-only")
    writer.write(output)
    writer.close()
    return output.getvalue()
