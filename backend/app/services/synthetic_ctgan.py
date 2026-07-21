"""SCRUM-16 — SDV / CTGAN ile sentetik veri üretimi.

SDV kütüphanesinin CTGANSynthesizer'ı kullanılarak anonim veri setindeki
istatistiksel ilişkiler öğrenilir ve bu ilişkilere uygun yeni (tamamen sahte)
kayıtlar üretilir.

Kurulum gereksinimleri (requirements.txt):
    sdv>=1.13
    torch  (SDV tarafından otomatik kurulur)

Kullanım:
    df_syn, stats = generate_synthetic_ctgan(df, num_rows=500, epochs=300)

Dönen değerler:
    df_syn : pandas.DataFrame  — üretilen sentetik kayıtlar
    stats  : dict              — kolon bazlı istatistiksel özet
"""

from __future__ import annotations

import logging

import pandas as pd

from app.services.comparison import compute_stats

logger = logging.getLogger(__name__)

# CTGAN import'u isteğe bağlı; yoksa ImportError fırlatılır ve
# router tarafında fallback tetiklenir.
try:
    from sdv.single_table import CTGANSynthesizer
    from sdv.metadata import SingleTableMetadata
    _SDV_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SDV_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────────────
# Ana fonksiyon
# ──────────────────────────────────────────────────────────────────────────────

def generate_synthetic_ctgan(
    df: pd.DataFrame,
    num_rows: int = 0,
    epochs: int = 300,
) -> tuple[pd.DataFrame, dict]:
    """CTGAN ile sentetik veri üretir.

    Parameters
    ----------
    df:
        Eğitim verisi (genellikle anonimleştirilmiş CSV).
    num_rows:
        Üretilecek satır sayısı. 0 → orijinal veri kadar.
    epochs:
        CTGAN eğitim epoch sayısı. Küçük veri setleri için 300 yeterlidir;
        büyük ve karmaşık veri setleri için artırılabilir.

    Returns
    -------
    df_syn:
        Üretilen sentetik veri çerçevesi.
    stats:
        Kolon bazlı istatistiksel karşılaştırma sözlüğü.

    Raises
    ------
    ImportError:
        SDV/CTGAN kurulu değilse.
    RuntimeError:
        Model eğitimi veya üretim sırasında hata oluşursa.
    """
    if not _SDV_AVAILABLE:
        raise ImportError(
            "SDV kütüphanesi kurulu değil. "
            "Kurmak için: pip install sdv"
        )

    n = num_rows if num_rows > 0 else len(df)
    logger.info("CTGAN eğitimi başlıyor: %d satır, %d epoch, %d hedef kayıt", len(df), epochs, n)

    # Metadata otomatik çıkar
    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(df)

    synthesizer = CTGANSynthesizer(metadata, epochs=epochs, verbose=True)

    try:
        synthesizer.fit(df)
        logger.info("CTGAN eğitimi tamamlandı, sentetik veri üretiliyor…")
        df_syn = synthesizer.sample(num_rows=n)
    except Exception as exc:
        logger.exception("CTGAN üretimi sırasında hata: %s", exc)
        raise RuntimeError(f"CTGAN üretimi başarısız: {exc}") from exc

    stats = compute_stats(df, df_syn)
    logger.info("CTGAN sentetik veri üretildi: %d satır", len(df_syn))
    return df_syn, stats
