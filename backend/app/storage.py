import logging
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"

# Yüklenen dosyalar (orijinal, anonim ve sentetik CSV'ler hepsi buraya
# yazılıyor) hiç silinmiyordu; disk üzerinde gerçek kişisel veri içeren
# dosyalar süresiz birikiyordu. Varsayılan olarak 24 saatten eski dosyaları
# temizliyoruz.
DEFAULT_MAX_AGE_HOURS = 24


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


def purge_expired(max_age_hours: float = DEFAULT_MAX_AGE_HOURS) -> int:
    """UPLOAD_DIR'da max_age_hours'tan eski .csv dosyalarını siler.

    Dönen değer: silinen dosya sayısı. Tek bir dosyanın silinmesi başarısız
    olursa (ör. başka bir process hâlâ okuyorsa) o dosya atlanır, işlem
    diğer dosyalar için devam eder.
    """
    if not UPLOAD_DIR.is_dir():
        return 0

    cutoff = time.time() - (max_age_hours * 3600)
    deleted = 0
    for path in UPLOAD_DIR.glob("*.csv"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                deleted += 1
        except OSError as exc:
            logger.warning("Süresi dolan dosya silinemedi: %s (%s)", path.name, exc)

    if deleted:
        logger.info("%d süresi dolmuş CSV dosyası silindi.", deleted)
    return deleted
