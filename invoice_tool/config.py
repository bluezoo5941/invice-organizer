import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_request_bytes: int = 80 * 1024 * 1024
    max_file_bytes: int = 10 * 1024 * 1024
    max_pdfs: int = 300
    worker_timeout: int = 90

    @classmethod
    def from_environment(cls):
        default = Path(__file__).resolve().parents[1] / "data"
        return cls(Path(os.environ.get("INVOICE_DATA_DIR", str(default))).resolve())
