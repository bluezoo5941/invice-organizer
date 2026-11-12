from collections import Counter, defaultdict

from .models import issue
from .parsing import parse_filename


def match_invoices(rows, files, notices, workbook_info):
    issues = list(notices)
    index = defaultdict(list)
    for file in files:
        if file.get("invalid_xref_references"):
            issues.append(
                issue(
                    "pdf_structure",
                    "合并副本会忽略无效的交叉引用流表单/批注引用，页面及原件保留。",
                    file=file["name"],
                    level="info",
                )
            )
        parsed = parse_filename(file["name"])
        if parsed:
            index[parsed].append(file)
            expected = f"{parsed[0]}-{parsed[1][:3]}-{parsed[1][3:]}.pdf"
            if file["name"] != expected:
                issues.append(
                    issue(
                        "normalized",
                        "已兼容文件名中的分隔符差异。",
                        file=file["name"],
                        level="info",
                    )
                )
        else:
            issues.append(issue("filename", "无法识别姓名和完整票号。", file=file["name"]))
        if file.get("error"):
            issues.append(issue("pdf_error", file["error"], file=file["name"]))
    ticket_counts = Counter(r.ticket for r in rows if r.ticket)
    groups = {}
    referenced = set()
    for row in rows:
        project = row.project or "未填写项目"
        group = groups.setdefault(
            project, {"project": project, "items": [], "pages": 0, "blocked": False}
        )
        item = row.to_dict()
        matches = index.get((row.name, row.ticket), [])
        error = row.error
        if not error and ticket_counts[row.ticket] > 1:
            error = "账单中票号重复或跨项目出现，请先确认归属。"
        if not error and len(matches) == 0:
            error = "找不到姓名和完整票号都一致的 PDF。"
        if not error and len(matches) > 1:
            error = "存在多份同姓名同票号 PDF，无法唯一匹配。"
        for f in matches:
            referenced.add(f["id"])
        if not error and matches[0].get("error"):
            error = matches[0]["error"]
        if error:
            item.update(status="blocked", error=error)
            group["blocked"] = True
            issues.append(issue("record", error, row=row.row, level="error"))
        else:
            f = matches[0]
            item.update(status="matched", file_id=f["id"], file=f["name"], pages=f["pages"])
            group["pages"] += f["pages"]
        group["items"].append(item)
    extras = [f for f in files if f["id"] not in referenced]
    for f in extras:
        if parse_filename(f["name"]):
            issues.append(
                issue("unmatched", "账单中没有对应记录，未分配到任何项目。", file=f["name"])
            )
    grouped = list(groups.values())
    for i, group in enumerate(grouped, 1):
        group["id"] = f"g{i:03}"
    return {
        "workbook": workbook_info,
        "summary": {
            "rows": len(rows),
            "pdfs": len(files),
            "matched": sum(x["status"] == "matched" for g in grouped for x in g["items"]),
            "groups": len(grouped),
            "ready_groups": sum(not g["blocked"] for g in grouped),
            "blocked_rows": sum(x["status"] == "blocked" for g in grouped for x in g["items"]),
            "unmatched_files": len(extras),
        },
        "groups": grouped,
        "issues": issues,
    }
