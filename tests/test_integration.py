import io
import re
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile

from pypdf import PdfReader

from invoice_tool.app import create_app
from invoice_tool.config import Settings
from invoice_tool.errors import UserError
from invoice_tool.repository import Repository

from .fixtures import pdf_bytes, workbook_bytes


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(Path(self.temp.name))
        self.app = create_app(self.settings)
        self.client = self.app.test_client()
        page = self.client.get("/")
        token = re.search(r'name="csrf-token" content="([^"]+)"', page.text)[1]
        self.headers = {"X-CSRF-Token": token}

    def tearDown(self):
        self.temp.cleanup()

    def upload(self, key=None, name="测试甲-784-1234567801.pdf", rows=None, pdf=None):
        return self.client.post(
            "/api/tasks",
            headers={**self.headers, "Idempotency-Key": key or uuid.uuid4().hex},
            data={
                "workbook": (io.BytesIO(workbook_bytes(rows)), "账单.xlsx"),
                "pdfs": (io.BytesIO(pdf if pdf is not None else pdf_bytes(2)), name),
            },
        )

    def test_real_end_to_end_and_reopen_database(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        task = response.json
        self.assertEqual(task["result"]["summary"]["matched"], 1)
        merged = self.client.post(f"/api/tasks/{task['id']}/export", headers=self.headers)
        self.assertEqual(merged.status_code, 200, merged.text)
        download = self.client.get(f"/api/tasks/{task['id']}/download", headers=self.headers)
        with ZipFile(io.BytesIO(download.data)) as zipfile:
            pdfs = [n for n in zipfile.namelist() if n.endswith(".pdf")]
            self.assertEqual(len(pdfs), 1)
            reader = PdfReader(io.BytesIO(zipfile.read(pdfs[0])))
            self.assertEqual([int(p.mediabox.width) for p in reader.pages], [300, 310])
            self.assertIn("归集明细.csv", zipfile.namelist())
        download.close()
        reopened = create_app(self.settings)
        persisted = reopened.extensions["repository"].get(task["id"])
        self.assertEqual(persisted["status"], "complete")
        self.assertEqual(persisted["result"]["exports"], merged.json["result"]["exports"])
        again = self.client.post(f"/api/tasks/{task['id']}/export", headers=self.headers)
        self.assertEqual(again.json["result"]["exports"], merged.json["result"]["exports"])

    def test_duplicate_upload_is_idempotent(self):
        key = uuid.uuid4().hex
        # XLSX is a ZIP with timestamps; reuse exactly the same request bytes.
        data = workbook_bytes()

        def submit():
            return self.client.post(
                "/api/tasks",
                headers={**self.headers, "Idempotency-Key": key},
                data={
                    "workbook": (io.BytesIO(data), "账单.xlsx"),
                    "pdfs": (io.BytesIO(pdf_bytes()), "测试甲-784-1234567801.pdf"),
                },
            )

        first, second = submit(), submit()
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json["id"], second.json["id"])
        self.assertEqual(len(self.app.extensions["repository"].list()), 1)

    def test_duplicate_key_different_input_rejected(self):
        key = uuid.uuid4().hex
        self.assertEqual(self.upload(key).status_code, 201)
        self.assertEqual(self.upload(key, pdf=pdf_bytes(3)).status_code, 409)

    def test_session_csrf_host_origin(self):
        self.assertEqual(self.app.test_client().get("/api/tasks").status_code, 403)
        self.assertEqual(self.client.get("/api/tasks").status_code, 403)
        self.assertEqual(
            self.client.get(
                "/api/tasks", headers={**self.headers, "Origin": "https://evil.example"}
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get("/", headers={"Host": "evil.example"}).status_code, 400)
        self.assertEqual(
            self.client.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403
        )

    def test_path_traversal_rejected(self):
        self.assertEqual(self.upload(name="../bad.pdf").status_code, 400)
        self.assertEqual(
            self.client.get("/api/tasks/invalid/download", headers=self.headers).status_code, 404
        )
        self.assertEqual(self.client.get("/data/records.sqlite3").status_code, 404)

    def test_sql_injection_is_data(self):
        attack = "x'); DROP TABLE tasks; --"
        row = ["784-1234567801", "测试甲", attack, ""]
        response = self.upload(rows=[row])
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json["result"]["groups"][0]["project"], attack)
        self.assertEqual(len(self.app.extensions["repository"].list()), 1)
        response = self.client.get("/api/tasks/%27%20OR%201=1--", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_invalid_pdf_blocks_export(self):
        response = self.upload(pdf=b"not pdf")
        task = response.json
        self.assertEqual(task["result"]["summary"]["ready_groups"], 0)
        exported = self.client.post(f"/api/tasks/{task['id']}/export", headers=self.headers)
        self.assertEqual(exported.status_code, 409)

    def test_payload_limit_and_unknown_fields(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 100
        self.assertEqual(self.upload().status_code, 413)
        self.app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024
        response = self.client.post("/api/tasks", headers=self.headers, data={"admin": "true"})
        self.assertEqual(response.status_code, 400)

    def test_get_download_before_complete(self):
        task = self.upload().json
        self.assertEqual(
            self.client.get(f"/api/tasks/{task['id']}/download", headers=self.headers).status_code,
            409,
        )

    def test_restart_recovery_preserves_ready_tasks(self):
        task = self.upload().json
        repo = self.app.extensions["repository"]
        repo.register(uuid.uuid4().hex, uuid.uuid4().hex, "a", "未完成.xlsx")
        self.assertEqual(repo.recover_interrupted(), 1)
        self.assertEqual(repo.get(task["id"])["status"], "ready")

    def test_concurrent_register_and_export_claim(self):
        repo = Repository(self.settings.data_dir / "records.sqlite3")
        key = uuid.uuid4().hex

        def register(_):
            return repo.register(uuid.uuid4().hex, key, "same", "并发.xlsx")

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(register, range(4)))
        self.assertEqual(sum(created for _, created in results), 1)
        task_id = results[0][0]["id"]
        repo.finish(task_id, "ready", {})
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda _: repo.claim_export(task_id), range(4)))
        self.assertEqual(sum(claims), 1)
        with self.assertRaises(UserError):
            repo.register(uuid.uuid4().hex, key, "changed", "并发.xlsx")
