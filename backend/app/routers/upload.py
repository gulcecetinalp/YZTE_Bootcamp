import io
import uuid

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile

from app.storage import UPLOAD_DIR, csv_path

router = APIRouter(prefix="/api", tags=["upload"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
PREVIEW_ROWS = 5


@router.post("/upload")
async def upload_csv(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Sadece .csv uzantılı dosyalar yüklenebilir.")

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Dosya boyutu 20 MB sınırını aşıyor.")

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Dosya geçerli bir CSV olarak okunamadı.")

    if df.empty or df.columns.empty:
        raise HTTPException(status_code=400, detail="CSV dosyası boş, işlenecek veri bulunamadı.")

    file_id = str(uuid.uuid4())
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path(file_id).write_bytes(contents)

    preview = df.head(PREVIEW_ROWS).where(df.head(PREVIEW_ROWS).notna(), None)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "num_rows": int(df.shape[0]),
        "num_columns": int(df.shape[1]),
        "columns": [
            {"name": str(name), "dtype": str(dtype)}
            for name, dtype in df.dtypes.items()
        ],
        "preview": preview.to_dict(orient="records"),
    }
