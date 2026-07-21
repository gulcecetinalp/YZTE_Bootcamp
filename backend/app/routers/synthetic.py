"""Sentetik veri üretim endpoint'leri.

SCRUM-16 (Task 9): CTGAN yöntemi  → method=ctgan
SCRUM-17 (Task 10): Faker yöntemi → method=faker

Varsayılan (method=auto): önce CTGAN denenir, başarısız olursa Faker devreye girer.
"""

import logging
import uuid
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.services.comparison import build_comparison_charts
from app.services.synthetic_faker import generate_synthetic_faker
from app.storage import csv_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["synthetic"])

PREVIEW_ROWS = 5


@router.post("/synthetic/{file_id}")
def generate_synthetic(
    file_id: str,
    method: Literal["ctgan", "faker", "auto"] = Query(
        default="auto",
        description=(
            "Kullanılacak sentetik veri üretim yöntemi: "
            "'ctgan' (SDV/CTGAN), 'faker' (istatistiksel + Faker) veya "
            "'auto' (önce CTGAN, hata varsa Faker)."
        ),
    ),
    num_rows: int = Query(
        default=0,
        ge=0,
        description="Üretilecek satır sayısı. 0 = orijinal veri kadar.",
    ),
    epochs: int = Query(
        default=300,
        ge=10,
        le=2000,
        description="Yalnızca CTGAN için geçerli eğitim epoch sayısı.",
    ),
):
    """Anonimleştirilmiş CSV'den sentetik veri üretir ve yeni bir dosyaya kaydeder.

    - **file_id**: Daha önce `/api/anonymize/{id}` endpoint'inden dönen
      `anonymized_file_id` değeri.
    - **method**: `ctgan` | `faker` | `auto`
    - **num_rows**: 0 → orijinal veri setindeki satır sayısı kadar üretir.
    - **epochs**: CTGAN eğitiminde kullanılacak epoch sayısı (sadece method=ctgan/auto).

    Sonuçlar:
    - `synthetic_file_id`: Yeni dosyanın ID'si — `uploads/<id>.csv` olarak saklanır.
    - `method_used`: Gerçekte hangi yöntemin kullanıldığı.
    - `stats`: Orijinal ve sentetik veri karşılaştırmalı istatistikleri.
    - `preview`: İlk 5 satırın önizlemesi.
    """
    source = csv_path(file_id)
    if not source.is_file():
        raise HTTPException(
            status_code=404,
            detail="Bu file_id ile kayıtlı bir CSV dosyası bulunamadı.",
        )

    try:
        df = pd.read_csv(source)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Kayıtlı dosya geçerli bir CSV olarak okunamadı.",
        )

    if df.empty:
        raise HTTPException(
            status_code=422,
            detail="Veri seti boş; sentetik veri üretilemiyor.",
        )

    df_syn: pd.DataFrame | None = None
    stats: dict = {}
    method_used: str = ""
    ctgan_error: str | None = None

    # ── CTGAN denemesi ────────────────────────────────────────────────────────
    if method in ("ctgan", "auto"):
        try:
            from app.services.synthetic_ctgan import generate_synthetic_ctgan
            df_syn, stats = generate_synthetic_ctgan(df, num_rows=num_rows, epochs=epochs)
            method_used = "ctgan"
            logger.info("CTGAN başarıyla kullanıldı (file_id=%s)", file_id)
        except ImportError as exc:
            ctgan_error = f"SDV kurulu değil: {exc}"
            logger.warning("CTGAN kullanılamıyor: %s", ctgan_error)
        except RuntimeError as exc:
            ctgan_error = str(exc)
            logger.warning("CTGAN başarısız oldu: %s", ctgan_error)
        except Exception as exc:
            ctgan_error = str(exc)
            logger.exception("CTGAN beklenmedik hata: %s", exc)

    # ── Faker fallback / doğrudan Faker ──────────────────────────────────────
    if df_syn is None:
        if method == "ctgan":
            # Kesinlikle CTGAN istendi ama başarısız oldu → hata döndür
            raise HTTPException(
                status_code=503,
                detail=(
                    f"CTGAN yöntemi kullanılamıyor: {ctgan_error}. "
                    "method=faker veya method=auto deneyebilirsiniz."
                ),
            )
        try:
            df_syn, stats = generate_synthetic_faker(df, num_rows=num_rows)
            method_used = "faker"
            if ctgan_error:
                logger.info("CTGAN başarısız oldu, Faker fallback kullanıldı.")
        except Exception as exc:
            logger.exception("Faker üretimi başarısız: %s", exc)
            raise HTTPException(
                status_code=500,
                detail=f"Sentetik veri üretimi başarısız oldu: {exc}",
            )

    # ── Sonucu kaydet ─────────────────────────────────────────────────────────
    synthetic_file_id = str(uuid.uuid4())
    df_syn.to_csv(csv_path(synthetic_file_id), index=False)

    preview_df = df_syn.head(PREVIEW_ROWS)
    preview = preview_df.where(preview_df.notna(), None)

    charts = build_comparison_charts(df, df_syn)

    return {
        "file_id": file_id,
        "synthetic_file_id": synthetic_file_id,
        "method_used": method_used,
        "ctgan_fallback_reason": ctgan_error,
        "num_rows": int(df_syn.shape[0]),
        "num_columns": int(df_syn.shape[1]),
        "stats": stats,
        "charts": charts,
        "preview": preview.to_dict(orient="records"),
    }
