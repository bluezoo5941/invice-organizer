"""Bounded child process for untrusted document parsing. No network or database."""

import json
import logging
import sys
from pathlib import Path

from .errors import UserError
from .matching import match_invoices
from .parsing import read_workbook
from .pdf_service import export_bundle, inspect_pdf


def run(mode, task_dir):
    manifest = json.loads((task_dir / "manifest.json").read_text("utf-8"))
    if mode == "analyze":
        rows, issues, info = read_workbook(task_dir / "source.xlsx", manifest["sheet"])
        files = [{**f, **inspect_pdf(task_dir / f["stored"])} for f in manifest["files"]]
        if sum(f.get("pages", 0) for f in files) > 2000:
            raise UserError("本批 PDF 超过 2,000 页，请拆分处理。")
        return match_invoices(rows, files, issues, info)
    if mode == "merge":
        result = json.loads((task_dir / "analysis.json").read_text("utf-8"))
        return export_bundle(task_dir, result, manifest["files"])
    raise ValueError("Unknown worker mode")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        output = {"ok": True, "result": run(sys.argv[1], Path(sys.argv[2]))}
    except UserError as exc:
        output = {"ok": False, "error": str(exc)}
    except Exception as exc:
        output = {
            "ok": False,
            "error": "文档处理失败，请检查文件是否完整或格式是否受支持。",
            "error_type": type(exc).__name__,
        }
    print(json.dumps(output, ensure_ascii=True))
