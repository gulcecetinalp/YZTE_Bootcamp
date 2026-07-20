import uuid

from fastapi import APIRouter, UploadFile

from app.services import validation
from app.storage import UPLOAD_DIR, csv_path

router = APIRouter(prefix="/api", tags=["upload"])

PREVIEW_ROWS = 5


@router.post("/upload")
async def upload_csv(file: UploadFile):
    # Validasyon adımlarını services/validation.py'ye taşıdık, burası artık
    # sadece "geçerliyse kaydet ve özet dön" işini yapıyor.
    validation.check_extension(file.filename)              # 1) uzantı .csv mi
    contents = await validation.read_within_limit(file)    # 2) boyut sınırını aşmadan oku
    df = validation.parse_csv(contents)                    # 3) pandas okuyabiliyor mu
    validation.validate_dataframe(df)                      # 4) boş/kolonsuz mu

    # buraya geldiysek dosya sağlam, diske yazıyoruz
    file_id = str(uuid.uuid4())
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    csv_path(file_id).write_bytes(contents)

    # ilk 5 satır önizleme. NaN'ları None'a çeviriyoruz yoksa JSON'da NaN
    # geçersiz oluyor ve frontend hata veriyor.
    head = df.head(PREVIEW_ROWS)
    preview = head.where(head.notna(), None)

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
