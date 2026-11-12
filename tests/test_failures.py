import dataclasses
import io
import json
import re
import tempfile
import unittest
import uuid
from pathlib import Path

from invoice_tool.app import create_app
from invoice_tool.config import Settings

from .fixtures import pdf_bytes, workbook_bytes


class FailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.temp.name))
        self.app = create_app(self.settings)
        self.client = self.app.test_client()
        token = re.search(r'name="csrf-token" content="([^"]+)"', self.client.get("/").text)[1]
        self.headers = {"X-CSRF-Token": token, "Idempotency-Key": uuid.uuid4().hex}

    def tearDown(self):
        self.temp.cleanup()

    def upload(self):
        return self.client.post(
            "/api/tasks",
            headers=self.headers,
            data={
                "workbook": (io.BytesIO(workbook_bytes()), "账单.xlsx"),
                "pdfs": (io.BytesIO(pdf_bytes(2)), "测试甲-784-1234567801.pdf"),
            },
        )

    def test_worker_timeout_is_explicit_and_persisted(self):
        self.app.extensions["task_service"].settings = dataclasses.replace(
            self.settings, worker_timeout=0
        )
        response = self.upload()
        self.assertEqual(response.status_code, 422, response.text)
        tasks = self.app.extensions["repository"].list()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "failed")
        self.assertIn("时间限制", tasks[0]["error"])

    def test_changed_pdf_fails_without_download(self):
        task = self.upload().json
        directory = self.settings.data_dir / "tasks" / task["id"]
        manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
        target = directory / manifest["files"][0]["stored"]
        target.write_bytes(target.read_bytes() + b"\n% modified after analysis\n")
        response = self.client.post(f"/api/tasks/{task['id']}/export", headers=self.headers)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("内容已变化", response.json["error"])
        self.assertEqual(
            self.client.get(f"/api/tasks/{task['id']}/download", headers=self.headers).status_code,
            409,
        )

    def test_database_failure_not_reported_as_success(self):
        # Replace only the storage with an intentionally missing table; no mocked success.
        with self.app.extensions["repository"].connection() as db:
            db.execute("DROP TABLE tasks")
        response = self.client.get("/api/tasks", headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("SELECT", response.text)
        self.assertNotIn("sqlite", response.text)
