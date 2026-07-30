import uuid
from pathlib import Path

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"


def csv_path(file_id: str) -> Path:
    return UPLOAD_DIR / f"{file_id}.csv"


def is_valid_file_id(file_id: str) -> bool:
    """file_id gerçekten bizim ürettiğimiz bir UUID mi?

    Ürettiğimiz bütün kimlikler uuid4 (upload, anonymize ve synthetic
    endpoint'lerinin hepsi str(uuid.uuid4()) kullanıyor). Bunu doğrulamak,
    dosya yolu oluşturulurken "../.." gibi değerlerin uploads/ klasörünün
    dışına çıkmasını baştan engelliyor.
    """
    try:
        uuid.UUID(file_id)
    except (ValueError, AttributeError, TypeError):
        return False
    return True
