"""CSV indirme endpoint'i.

Ürün anonimleştirilmiş ve sentetik veri setleri üretiyordu ama kullanıcı
bunları yalnızca ilk 5 satırlık önizleme olarak görebiliyordu; dosyayı
alamıyordu. Bu endpoint üretilen CSV'yi indirilebilir hale getiriyor.
"""

import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.storage import csv_path, is_valid_file_id

router = APIRouter(prefix="/api", tags=["download"])

# İndirilen dosyanın adında yalnızca bu karakterlere izin veriyoruz. Amaç,
# kullanıcıdan gelen bir metnin Content-Disposition başlığına satır sonu veya
# tırnak sokmasını engellemek.
_SAFE_LABEL_PATTERN = re.compile(r"[^A-Za-z0-9-]")
_DEFAULT_LABEL = "veri"


@router.get("/download/{file_id}")
def download_csv(
    file_id: str,
    label: str = Query(
        default=_DEFAULT_LABEL,
        max_length=40,
        description="İndirilen dosya adında kullanılacak kısa etiket (ör. anonim, sentetik).",
    ),
):
    """Kayıtlı bir CSV dosyasını indirir.

    - **file_id**: upload, anonymize veya synthetic adımlarından dönen kimlik.
    - **label**: dosya adına eklenecek etiket; güvenlik için sadece harf,
      rakam ve tire karakterleri korunur.
    """
    if not is_valid_file_id(file_id):
        raise HTTPException(status_code=400, detail="Geçersiz dosya kimliği.")

    source = csv_path(file_id)
    if not source.is_file():
        raise HTTPException(
            status_code=404,
            detail="Bu file_id ile kayıtlı bir dosya bulunamadı.",
        )

    safe_label = _SAFE_LABEL_PATTERN.sub("", label) or _DEFAULT_LABEL
    filename = f"aegisai-{safe_label}-{file_id[:8]}.csv"

    return FileResponse(path=source, media_type="text/csv", filename=filename)
