import hashlib
import re
from pathlib import Path

from .errors import UserError


def validate_name(name, extension):
    if (
        not name
        or len(name) > 200
        or "/" in name
        or "\\" in name
        or any(ord(c) < 32 for c in name)
        or Path(name).suffix.lower() != extension
    ):
        raise UserError(f"请选择有效的 {extension} 文件，文件名不能包含路径或控制字符。")
    return name


def save_upload(upload, target, max_bytes):
    total = 0
    digest = hashlib.sha256()
    with target.open("wb") as stream:
        while block := upload.stream.read(65536):
            total += len(block)
            if total > max_bytes:
                raise UserError("单个文件不能超过 10 MB。", 413)
            stream.write(block)
            digest.update(block)
    if not total:
        raise UserError("不能上传空文件。")
    return digest.hexdigest()


def task_path(root, task_id):
    if not re.fullmatch(r"[a-f0-9]{32}", task_id):
        raise UserError("任务标识无效。", 404)
    return root / "tasks" / task_id
