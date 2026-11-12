import csv
import hashlib
import re
from contextlib import ExitStack
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject

from .errors import UserError


def clean_xref_references(reader):
    """Drop only invalid XRef-stream references used as annotations/form fields.

    Never flatten, remove real widgets, or rewrite a source file. Some supplier
    PDFs reference their cross-reference stream in place of a field dictionary.
    """
    count = 0
    root = reader.trailer["/Root"]
    form = root.get("/AcroForm")
    targets = [(page, "/Annots") for page in reader.pages]
    if form is not None:
        targets.append((form.get_object(), "/Fields"))
    for owner, key in targets:
        refs = owner.get(key)
        if refs is None:
            continue
        refs = refs.get_object()
        kept = []
        for ref in refs:
            obj = ref.get_object()
            if isinstance(obj, dict) and obj.get("/Type") == "/XRef":
                count += 1
            else:
                kept.append(ref)
        if len(kept) != len(refs):
            owner[NameObject(key)] = ArrayObject(kept)
    return count


def inspect_pdf(path):
    try:
        with path.open("rb") as stream:
            if not stream.read(5) == b"%PDF-":
                return {"error": "文件内容不是 PDF。"}
            stream.seek(0)
            reader = PdfReader(stream)
            if reader.is_encrypted:
                return {"error": "PDF 已加密，请提供未加密副本。"}
            pages = len(reader.pages)
            if not 1 <= pages <= 200:
                return {"error": "单个 PDF 必须包含 1–200 页。"}
            return {"pages": pages, "invalid_xref_references": clean_xref_references(reader)}
    except Exception:
        # Invalid third-party documents have varied parser exceptions. This is an
        # explicit per-file failure, not a successful fallback; content is not logged.
        return {"error": "PDF 结构损坏或当前解析器无法读取。"}


def safe_filename(project, group_id):
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", project).strip(" .")[:100] or "未命名"
    return f"{group_id}_{stem}.pdf"


def csv_cell(value):
    text = str(value if value is not None else "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def write_csv(path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows([[csv_cell(v) for v in row] for row in rows])


def export_bundle(task_dir: Path, result, files):
    index = {f["id"]: f for f in files}
    outdir = task_dir / "export"
    outdir.mkdir(exist_ok=True)
    generated, detail = [], []
    for group in result["groups"]:
        if group["blocked"]:
            for item in group["items"]:
                detail.append(
                    [
                        group["project"],
                        item["row"],
                        item["name"],
                        item["ticket"],
                        item.get("file", ""),
                        "",
                        "",
                        "项目存在异常，未导出",
                    ]
                )
            continue
        filename = safe_filename(group["project"], group["id"])
        target = outdir / filename
        writer = PdfWriter()
        page = 1
        try:
            with ExitStack() as stack:
                for item in group["items"]:
                    file = index[item["file_id"]]
                    stream = stack.enter_context((task_dir / file["stored"]).open("rb"))
                    if hashlib.file_digest(stream, "sha256").hexdigest() != file["sha256"]:
                        raise UserError("PDF 内容已变化，请重新分析。")
                    stream.seek(0)
                    reader = PdfReader(stream)
                    if reader.is_encrypted or len(reader.pages) != item["pages"]:
                        raise UserError("PDF 内容已变化，请重新分析。")
                    clean_xref_references(reader)
                    writer.append(reader, import_outline=False)
                    detail.append(
                        [
                            group["project"],
                            item["row"],
                            item["name"],
                            item["ticket"],
                            file["name"],
                            page,
                            page + item["pages"] - 1,
                            "已导出",
                        ]
                    )
                    page += item["pages"]
                with target.open("wb") as stream:
                    writer.write(stream)
            with target.open("rb") as stream:
                if len(PdfReader(stream).pages) != group["pages"]:
                    raise UserError("导出后的页数校验失败。")
            generated.append(
                {
                    "group_id": group["id"],
                    "project": group["project"],
                    "filename": filename,
                    "pages": group["pages"],
                }
            )
        finally:
            writer.close()
    if not generated:
        raise UserError("没有资料完整的项目可导出，请先处理异常。", 409)
    write_csv(
        outdir / "归集明细.csv",
        ["项目", "表格行", "姓名", "完整票号", "源文件", "起始页", "结束页", "状态"],
        detail,
    )
    write_csv(
        outdir / "异常与清洗记录.csv",
        ["级别", "类别", "表格行", "文件名", "说明"],
        [[i["level"], i["kind"], i["row"], i["file"], i["message"]] for i in result["issues"]],
    )
    with ZipFile(outdir / "项目发票.zip.part", "w", compression=ZIP_DEFLATED) as archive:
        for f in generated:
            archive.write(outdir / f["filename"], f["filename"])
        for name in ("归集明细.csv", "异常与清洗记录.csv"):
            archive.write(outdir / name, name)
    (outdir / "项目发票.zip.part").replace(outdir / "项目发票.zip")
    return generated
