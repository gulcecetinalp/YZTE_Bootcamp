"""SCRUM-17 — Faker + istatistiksel kural tabanlı alternatif sentetik veri üretimi.

Bu modül SDV/CTGAN'ın kurulu olmadığı ya da çalışmadığı durumlarda devreye giren
yedek (fallback) yöntemdir.  Hiçbir ML modeli gerektirmez; yalnızca
scipy, numpy ve Faker kütüphanelerine ihtiyaç duyar.

Strateji:
    - Sayısal kolonlar   → Gerçek dağılım (mean/std) korunarak truncated-normal
                           örnekleme (scipy.stats.truncnorm).  Tam sayı kolonlarda
                           sonuç yuvarlama yapılır.
    - Kategorik kolonlar → Orijinal frekans dağılımı korunarak rastgele örnekleme.
    - Boolean kolonlar   → True/False oranı korunarak Bernoulli örnekleme.
    - Tarih/zaman        → Gerçek min-max aralığında düzgün dağılım.
    - Metin / karma      → Faker ile dil ve context'e uygun sentetik değer.

Kullanım:
    df_syn, stats = generate_synthetic_faker(df, num_rows=500)

Dönen değerler:
    df_syn : pandas.DataFrame  — üretilen sentetik kayıtlar
    stats  : dict              — kolon bazlı istatistiksel özet
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.services.comparison import compute_stats

logger = logging.getLogger(__name__)

# Faker isteğe bağlı; yoksa metin kolonları için basit placeholder kullanılır.
try:
    from faker import Faker
    _faker = Faker("tr_TR")
    Faker.seed(42)
    _FAKER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FAKER_AVAILABLE = False
    logger.warning("Faker kurulu değil; metin kolonlar için placeholder kullanılacak.")

# scipy.stats isteğe bağlı; yoksa numpy normal örnekleme yapılır.
try:
    from scipy.stats import truncnorm
    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SCIPY_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# Kolon tipi tespiti (yardımcılar)
# ──────────────────────────────────────────────────────────────────────────────

_COLUMN_FAKER_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"name|isim|ad\b", re.I), "name"),
    (re.compile(r"surname|soyad", re.I), "last_name"),
    (re.compile(r"email|eposta|mail", re.I), "email"),
    (re.compile(r"phone|telefon|tel\b|gsm|mobile", re.I), "phone_number"),
    (re.compile(r"address|adres", re.I), "address"),
    (re.compile(r"city|sehir|il\b", re.I), "city"),
    (re.compile(r"country|ulke|country", re.I), "country"),
    (re.compile(r"company|sirket|firma", re.I), "company"),
    (re.compile(r"job|meslek|pozisyon", re.I), "job"),
    (re.compile(r"iban", re.I), "iban"),
    (re.compile(r"url|website|site", re.I), "url"),
]


def _faker_method(column_name: str) -> str | None:
    """Kolon adına göre Faker yöntemi döndürür."""
    for pattern, method in _COLUMN_FAKER_MAP:
        if pattern.search(column_name):
            return method
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Örnekleme fonksiyonları
# ──────────────────────────────────────────────────────────────────────────────

def _sample_numeric(series: pd.Series, n: int) -> np.ndarray:
    """Truncated normal dağılım ile sayısal örnekleme."""
    col_min = float(series.min())
    col_max = float(series.max())
    mean = float(series.mean())
    std = float(series.std()) or 1.0  # std=0 patlamasını önle

    if _SCIPY_AVAILABLE:
        a = (col_min - mean) / std
        b = (col_max - mean) / std
        samples = truncnorm.rvs(a, b, loc=mean, scale=std, size=n)
    else:
        samples = np.random.normal(loc=mean, scale=std, size=n)
        samples = np.clip(samples, col_min, col_max)

    # Tam sayı kolonları için yuvarla
    if pd.api.types.is_integer_dtype(series):
        samples = np.round(samples).astype(series.dtype)

    return samples


def _sample_categorical(series: pd.Series, n: int) -> np.ndarray:
    """Frekans dağılımını koruyarak kategorik örnekleme."""
    vc = series.value_counts(normalize=True)
    return np.random.choice(vc.index.tolist(), size=n, p=vc.values)


def _sample_boolean(series: pd.Series, n: int) -> np.ndarray:
    """True oranını koruyarak boolean örnekleme."""
    p_true = float(series.mean())
    return np.random.random(n) < p_true


def _sample_datetime(series: pd.Series, n: int) -> list[Any]:
    """Min-max aralığında düzgün dağılımlı tarih üretimi."""
    dt_series = pd.to_datetime(series, errors="coerce").dropna()
    if dt_series.empty:
        return [None] * n
    t_min = dt_series.min().timestamp()
    t_max = dt_series.max().timestamp()
    samples = np.random.uniform(t_min, t_max, n)
    return [datetime.fromtimestamp(t).strftime("%Y-%m-%d") for t in samples]


def _sample_text_faker(column_name: str, n: int) -> list[str]:
    """Faker ile metin üretimi."""
    if not _FAKER_AVAILABLE:
        return [f"SYNTH_{i}" for i in range(n)]
    method = _faker_method(column_name)
    if method and hasattr(_faker, method):
        fn = getattr(_faker, method)
        return [str(fn()) for _ in range(n)]
    # Genel metin için word
    return [str(_faker.word()) for _ in range(n)]


# ──────────────────────────────────────────────────────────────────────────────
# Ana fonksiyon
# ──────────────────────────────────────────────────────────────────────────────

def generate_synthetic_faker(
    df: pd.DataFrame,
    num_rows: int = 0,
    random_state: int = 42,
) -> tuple[pd.DataFrame, dict]:
    """Faker + istatistiksel kural tabanlı sentetik veri üretir.

    Parameters
    ----------
    df:
        Eğitim verisi (genellikle anonimleştirilmiş CSV).
    num_rows:
        Üretilecek satır sayısı. 0 → orijinal veri kadar.
    random_state:
        Tekrar üretilebilirlik için rastgelelik tohumu.

    Returns
    -------
    df_syn:
        Üretilen sentetik veri çerçevesi.
    stats:
        Kolon bazlı istatistiksel karşılaştırma sözlüğü.
    """
    np.random.seed(random_state)
    n = num_rows if num_rows > 0 else len(df)
    logger.info("Faker tabanlı sentetik üretim başlıyor: %d hedef kayıt", n)

    synthetic_data: dict[str, Any] = {}

    for col in df.columns:
        series = df[col].dropna()

        if series.empty:
            synthetic_data[col] = [None] * n
            continue

        # Boolean
        if pd.api.types.is_bool_dtype(series):
            synthetic_data[col] = _sample_boolean(series, n)

        # Sayısal
        elif pd.api.types.is_numeric_dtype(series):
            synthetic_data[col] = _sample_numeric(series, n)

        # Tarih/zaman
        elif pd.api.types.is_datetime64_any_dtype(series) or (
            series.dtype == object and _looks_like_date(series)
        ):
            synthetic_data[col] = _sample_datetime(series, n)

        # Az sayıda benzersiz değer (kategorik gibi davran)
        elif series.dtype == object and series.nunique() <= max(20, len(series) * 0.05):
            synthetic_data[col] = _sample_categorical(series, n)

        # Metin — Faker
        else:
            synthetic_data[col] = _sample_text_faker(col, n)

    df_syn = pd.DataFrame(synthetic_data)
    stats = compute_stats(df, df_syn)
    logger.info("Faker sentetik veri üretildi: %d satır", len(df_syn))
    return df_syn, stats


def _looks_like_date(series: pd.Series, sample: int = 100) -> bool:
    """Seriyi tarihe dönüştürmeyi deneyerek tarih içerip içermediğini tahmin eder."""
    try:
        converted = pd.to_datetime(series.head(sample), errors="coerce", format="mixed")
        return converted.notna().mean() > 0.7
    except Exception:
        return False
