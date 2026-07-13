from pathlib import Path

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"


def csv_path(file_id: str) -> Path:
    return UPLOAD_DIR / f"{file_id}.csv"
