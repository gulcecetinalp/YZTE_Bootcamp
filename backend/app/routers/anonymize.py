import uuid

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.services.anonymization import anonymize_dataframe
from app.services.detection import detect_sensitive_columns
from app.storage import csv_path

router = APIRouter(prefix="/api", tags=["anonymize"])

PREVIEW_ROWS = 5


@router.post("/anonymize/{file_id}")
def anonymize_file(file_id: str):
    """Yüklenmiş CSV'deki hassas kolonları tespit edip anonimleştirir.

    Anonim veri seti yeni bir file_id ile uploads/ altına kaydedilir;
    sonraki adımlar (sentetik veri üretimi) bu id üzerinden çalışabilir.
    """
    source = csv_path(file_id)
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Bu file_id ile yüklenmiş bir dosya bulunamadı.")

    try:
        df = pd.read_csv(source)
    except Exception:
        raise HTTPException(status_code=400, detail="Kayıtlı dosya geçerli bir CSV olarak okunamadı.")

    detections = detect_sensitive_columns(df)
    anonymized_df, actions = anonymize_dataframe(df, detections)

    anonymized_file_id = str(uuid.uuid4())
    anonymized_df.to_csv(csv_path(anonymized_file_id), index=False)

    preview_df = anonymized_df.head(PREVIEW_ROWS)
    preview = preview_df.where(preview_df.notna(), None)

    return {
        "file_id": file_id,
        "anonymized_file_id": anonymized_file_id,
        "num_rows": int(anonymized_df.shape[0]),
        "num_columns": int(anonymized_df.shape[1]),
        "detections": detections,
        "actions": actions,
        "preview": preview.to_dict(orient="records"),
    }
