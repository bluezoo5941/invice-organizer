import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .errors import UserError


def now():
    return datetime.now(UTC).isoformat()


class Repository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            script = (Path(__file__).parent / "migrations/001_initial.sql").read_text("utf-8")
            db.executescript("BEGIN IMMEDIATE;\n" + script + "\nCOMMIT;")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            return None
        item = dict(row)
        raw_result = item.pop("result_json")
        item["result"] = json.loads(raw_result) if raw_result else None
        item.pop("request_key", None)
        item.pop("fingerprint", None)
        return item

    def register(self, task_id, request_key, fingerprint, name):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM tasks WHERE request_key=?", (request_key,)
            ).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise UserError("同一个提交标识不能用于不同文件，请重新提交。", 409)
                return self.decode(existing), False
            stamp = now()
            db.execute(
                "INSERT INTO tasks(id,request_key,fingerprint,name,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (task_id, request_key, fingerprint, name, "analyzing", stamp, stamp),
            )
        return self.get(task_id), True

    def get(self, task_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise UserError("找不到该任务。", 404)
        return self.decode(row)

    def list(self, limit=50, offset=0):
        with self.connection() as db:
            rows = db.execute(
                "SELECT id,name,status,created_at,updated_at,error FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def finish(self, task_id, status, result=None, error=None):
        if status not in {"ready", "complete", "failed"}:
            raise ValueError("Invalid final status")
        with self.connection() as db:
            db.execute(
                "UPDATE tasks SET status=?,result_json=COALESCE(?,result_json),error=?,updated_at=? WHERE id=?",
                (
                    status,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error,
                    now(),
                    task_id,
                ),
            )

    def claim_export(self, task_id):
        with self.connection() as db:
            updated = db.execute(
                "UPDATE tasks SET status='merging',updated_at=? WHERE id=? AND status='ready'",
                (now(), task_id),
            ).rowcount
        return updated == 1

    def recover_interrupted(self):
        with self.connection() as db:
            return db.execute(
                "UPDATE tasks SET status='failed',error=?,updated_at=? WHERE status IN ('analyzing','merging')",
                ("上次处理被中断，原文件副本仍保留，请重新导入。", now()),
            ).rowcount
