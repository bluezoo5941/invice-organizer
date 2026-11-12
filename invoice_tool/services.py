import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path

from .errors import UserError
from .storage import save_upload, task_path, validate_name

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, settings, repository):
        self.settings = settings
        self.repository = repository
        self.slots = threading.BoundedSemaphore(2)
        (settings.data_dir / "tasks").mkdir(parents=True, exist_ok=True)
        (settings.data_dir / "staging").mkdir(exist_ok=True)

    def worker(self, mode, directory):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "invoice_tool.worker", mode, str(directory)],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.settings.worker_timeout,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            output = json.loads(proc.stdout)
        except subprocess.TimeoutExpired as exc:
            raise UserError("处理超过时间限制，请拆分文件后重新导入。", 422) from exc
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            logger.error("worker failure: %s", type(exc).__name__)
            raise UserError("文档处理进程未能完成，请重新导入。", 422) from exc
        if not output["ok"]:
            logger.warning(
                "document processing failure: %s", output.get("error_type", "invalid_document")
            )
            raise UserError(output["error"], 422)
        return output["result"]

    def create(self, workbook, pdfs, sheet, request_key):
        if not re.fullmatch(r"[a-zA-Z0-9-]{16,64}", request_key or ""):
            raise UserError("提交标识无效，请刷新后重试。")
        if not workbook or not 1 <= len(pdfs) <= self.settings.max_pdfs:
            raise UserError("需要一份 Excel 和 1–300 份 PDF。")
        if len(sheet) > 100:
            raise UserError("工作表名称过长。")
        name = validate_name(workbook.filename, ".xlsx")
        if not self.slots.acquire(blocking=False):
            raise UserError("已有任务正在处理，请稍后重试。", 429)
        task_id = None
        try:
            with tempfile.TemporaryDirectory(dir=self.settings.data_dir / "staging") as temp:
                stage = Path(temp)
                digest = save_upload(workbook, stage / "source.xlsx", self.settings.max_file_bytes)
                files = []
                for upload in pdfs:
                    filename = validate_name(upload.filename, ".pdf")
                    file_id = uuid.uuid4().hex
                    stored = file_id + ".pdf"
                    file_hash = save_upload(upload, stage / stored, self.settings.max_file_bytes)
                    files.append(
                        {"id": file_id, "name": filename, "stored": stored, "sha256": file_hash}
                    )
                identity = [digest, sheet, sorted((f["name"], f["sha256"]) for f in files)]
                fingerprint = hashlib.sha256(
                    json.dumps(identity, ensure_ascii=True).encode()
                ).hexdigest()
                proposed_id = uuid.uuid4().hex
                task, created = self.repository.register(
                    proposed_id, request_key, fingerprint, name
                )
                if not created:
                    return task
                task_id = proposed_id
                directory = task_path(self.settings.data_dir, task_id)
                directory.mkdir()
                for source in stage.iterdir():
                    source.replace(directory / source.name)
                manifest = {"sheet": sheet, "files": files}
                (directory / "manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=False), "utf-8"
                )
            result = self.worker("analyze", directory)
            (directory / "analysis.json").write_text(
                json.dumps(result, ensure_ascii=False), "utf-8"
            )
            self.repository.finish(task_id, "ready", result)
            return self.repository.get(task_id)
        except UserError as exc:
            if task_id:
                self.repository.finish(task_id, "failed", error=str(exc))
            raise
        except Exception:
            if task_id:
                self.repository.finish(task_id, "failed", error="处理未能完成，请重新导入。")
            raise
        finally:
            self.slots.release()

    def export(self, task_id):
        task_path(self.settings.data_dir, task_id)
        task = self.repository.get(task_id)
        if task["status"] == "complete":
            return task
        if task["status"] != "ready":
            raise UserError("任务尚未就绪或正在处理，请刷新状态。", 409)
        if not task["result"]["summary"]["ready_groups"]:
            raise UserError("没有资料完整的项目，请修正异常后重新导入。", 409)
        if not self.slots.acquire(blocking=False):
            raise UserError("已有任务正在处理，请稍后重试。", 429)
        claimed = False
        try:
            claimed = self.repository.claim_export(task_id)
            if not claimed:
                raise UserError("该任务已经开始处理，请稍后刷新。", 409)
            generated = self.worker("merge", task_path(self.settings.data_dir, task_id))
            result = task["result"]
            result["exports"] = generated
            self.repository.finish(task_id, "complete", result)
            return self.repository.get(task_id)
        except UserError as exc:
            if claimed:
                self.repository.finish(task_id, "failed", error=str(exc))
            raise
        except Exception:
            if claimed:
                self.repository.finish(task_id, "failed", error="合并未完成，请重新导入。")
            raise
        finally:
            self.slots.release()

    def workbook_download(self, task_id):
        directory = task_path(self.settings.data_dir, task_id)
        task = self.repository.get(task_id)
        path = directory / "source.xlsx"
        if not path.is_file():
            raise UserError("找不到该任务保存的 Excel。", 410)
        return path, task["name"]

    def download(self, task_id, group_id=None):
        directory = task_path(self.settings.data_dir, task_id)
        task = self.repository.get(task_id)
        if task["status"] != "complete":
            raise UserError("导出尚未完成。", 409)
        filename = "项目发票.zip"
        if group_id:
            matches = [f for f in task["result"]["exports"] if f["group_id"] == group_id]
            if len(matches) != 1:
                raise UserError("找不到该项目导出。", 404)
            filename = matches[0]["filename"]
        path = directory / "export" / filename
        if not path.is_file():
            raise UserError("导出文件已被移动或删除，请重新导入生成。", 410)
        return path
