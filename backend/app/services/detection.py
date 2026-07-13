"""Hassas veri tespiti: kolon adı analizi + içerik regex taraması.

İki sinyal birleştirilir:
1. Kolon adı analizi — kolon adı token'lara ayrılıp (camelCase / snake_case /
   boşluk) Türkçe-İngilizce anahtar kelime sözlüğüyle eşleştirilir.
2. İçerik regex taraması — metin kolonlarında e-posta, telefon, TCKN, IBAN ve
   kart numarası desenleri örneklem üzerinde aranır.

Kategoriler iki duyarlılık seviyesine ayrılır:
- "direct": kişiyi doğrudan tanımlar (isim, ID, e-posta...) → anonimleştirilir.
- "quasi": tek başına tanımlamaz ama birleşince riskli (yaş, cinsiyet, konum)
  → raporlanır; genelleştirme sentetik veri aşamasında ele alınacak.
"""

import re

import pandas as pd

# Kolon adı token'ı -> kategori. Sıra önemli: ilk eşleşen kazanır.
_TOKEN_CATEGORIES: list[tuple[set[str], str]] = [
    ({"tckn", "kimlik", "ssn", "identity"}, "national_id"),
    ({"iban"}, "iban"),
    ({"email", "eposta", "mail"}, "email"),
    ({"phone", "telefon", "tel", "gsm", "mobile"}, "phone"),
    ({"surname", "soyad", "soyadi", "lastname"}, "name"),
    ({"name", "isim", "firstname", "fullname"}, "name"),
    ({"address", "adres"}, "address"),
    ({"id", "customerid"}, "id"),
    ({"geography", "country", "city", "location", "ulke", "sehir", "il"}, "location"),
    ({"gender", "cinsiyet", "sex"}, "gender"),
    ({"age", "yas"}, "age"),
    ({"birth", "dogum", "birthdate"}, "birthdate"),
]

QUASI_CATEGORIES = {"location", "gender", "age", "birthdate"}

# İçerik desenleri: (kategori, derlenmiş regex). Tam hücre eşleşmesi aranır.
_CONTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")),
    ("iban", re.compile(r"^TR\d{24}$")),
    ("national_id", re.compile(r"^[1-9]\d{10}$")),
    ("card_number", re.compile(r"^(?:\d[ -]?){13,19}$")),
    (
        "phone",
        re.compile(r"^(\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}$"),
    ),
]

_CONTENT_SAMPLE_SIZE = 500
_CONTENT_MATCH_THRESHOLD = 0.5


def _column_tokens(column_name: str) -> set[str]:
    """Kolon adını küçük harfli token'lara ayırır: 'CustomerId' -> {'customer', 'id'}."""
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", column_name)
    return {p.lower() for p in parts}


def _match_column_name(column_name: str) -> str | None:
    tokens = _column_tokens(column_name)
    for keywords, category in _TOKEN_CATEGORIES:
        if tokens & keywords:
            return category
    return None


def _match_content(series: pd.Series) -> tuple[str, float] | None:
    sample = series.dropna().astype(str).str.strip().head(_CONTENT_SAMPLE_SIZE)
    if sample.empty:
        return None
    for category, pattern in _CONTENT_PATTERNS:
        ratio = sample.str.fullmatch(pattern).mean()
        if ratio >= _CONTENT_MATCH_THRESHOLD:
            return category, float(ratio)
    return None


def detect_sensitive_columns(df: pd.DataFrame) -> list[dict]:
    """Veri çerçevesindeki hassas kolonları tespit eder.

    Dönen her kayıt: column, category, sensitivity (direct|quasi),
    detected_by (column_name|content_pattern), match_ratio (içerik taramasında).
    """
    detections: list[dict] = []

    for column in df.columns:
        category = _match_column_name(str(column))
        detected_by = "column_name"
        match_ratio = None

        if category is None and df[column].dtype == object:
            content_match = _match_content(df[column])
            if content_match is not None:
                category, match_ratio = content_match
                detected_by = "content_pattern"

        if category is None:
            continue

        detections.append(
            {
                "column": str(column),
                "category": category,
                "sensitivity": "quasi" if category in QUASI_CATEGORIES else "direct",
                "detected_by": detected_by,
                "match_ratio": match_ratio,
            }
        )

    return detections
