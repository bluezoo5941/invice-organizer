import re
import unicodedata
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import openpyxl

from .errors import UserError
from .models import InvoiceRow, issue

ALIASES = {
    "ticket": {"票号", "机票票号", "电子客票号"},
    "name": {"乘机人姓名", "乘机人", "姓名", "员工姓名"},
    "project": {"项目名称", "项目号", "项目编号", "项目编码"},
}


def clean(value):
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def normalize_ticket(value):
    if isinstance(value, bool):
        return ""
    if isinstance(value, float):
        if not value.is_integer():
            return ""
        value = int(value)
    text = clean(value).replace("－", "-").replace("–", "-").replace("—", "-")
    if not re.fullmatch(r"[0-9]{3}[-\s]?[0-9]{10}", text):
        return ""
    return re.sub(r"[-\s]", "", text)


def parse_filename(filename):
    stem = clean(Path(filename).stem).replace("–", "-").replace("—", "-")
    match = re.fullmatch(r"(.+?)[_\s-]?([0-9]{3})[_\s-]?([0-9]{10})", stem)
    if not match:
        return None
    name = match[1].strip()
    if not name or name[-1:] in "-_":
        return None
    return name, match[2] + match[3]


def validate_xlsx(path):
    try:
        with ZipFile(path) as archive:
            parts = archive.infolist()
            if len(parts) > 2000 or sum(p.file_size for p in parts) > 40 * 1024 * 1024:
                raise UserError("Excel 解压后过大，请拆分后处理。")
            if any(p.flag_bits & 1 for p in parts):
                raise UserError("不支持加密 Excel。")
            if "xl/workbook.xml" not in archive.namelist():
                raise UserError("文件不是有效的 .xlsx 工作簿。")
            if any(p.filename.lower().endswith("vbaproject.bin") for p in parts):
                raise UserError("不支持包含宏的工作簿。")
    except BadZipFile as exc:
        raise UserError("Excel 无法读取，请选择未加密的 .xlsx 文件。") from exc


def read_workbook(path, sheet_name=""):
    validate_xlsx(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        candidates = []
        for ws in wb:
            if sheet_name and ws.title != sheet_name:
                continue
            if ws.max_column > 100 or ws.max_row > 20001:
                raise UserError("工作表超过限制：最多 100 列、20,000 条记录。")
            for row in ws.iter_rows(max_row=min(ws.max_row, 30), values_only=False):
                columns = {}
                for field, aliases in ALIASES.items():
                    found = [c.column for c in row if re.sub(r"\s", "", clean(c.value)) in aliases]
                    if len(found) == 1:
                        columns[field] = found[0]
                if len(columns) == 3:
                    candidates.append((ws, row[0].row, columns))
                    break
        if len(candidates) != 1:
            names = "、".join(x[0].title for x in candidates)
            raise UserError(
                f"找到多个数据表（{names}），请填写要使用的工作表名称。"
                if candidates
                else "未找到唯一的票号、乘机人姓名和项目字段，请检查工作表名称与前 30 行表头。"
            )
        ws, header, columns = candidates[0]
        rows, notices = [], []
        for cells in ws.iter_rows(min_row=header + 1):
            values = {key: cells[col - 1] for key, col in columns.items()}
            if all(c.value is None for c in cells):
                continue
            errors = []
            if any(c.data_type == "f" for c in values.values()):
                errors.append("关键字段含公式，请在原表副本中转换为明确文本")
            name, project = clean(values["name"].value), clean(values["project"].value)
            ticket = normalize_ticket(values["ticket"].value)
            if not name or len(name) > 100:
                errors.append("姓名为空或过长")
            if not ticket:
                errors.append("票号应为完整 13 位数字，可含中间连接符")
            if not project or len(project) > 150:
                errors.append("项目为空或过长")
            number = cells[0].row
            rows.append(InvoiceRow(number, name, ticket, project, "；".join(errors)))
            if project != str(values["project"].value or ""):
                notices.append(
                    issue("normalized", "已统一项目名称格式和首尾空格。", row=number, level="info")
                )
        if not rows:
            raise UserError("工作表中没有可处理的记录。")
        return rows, notices, {"sheet": ws.title, "header_row": header, "columns": columns}
    finally:
        wb.close()
