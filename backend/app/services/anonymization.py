"""Tespit edilen hassas kolonların anonimleştirilmesi.

Kategori bazlı stratejiler:
- id           -> SHA-256 hash (ilk 12 karakter): kayıtlar arası eşleşme
                  (joinability) korunur ama gerçek kimlik geri döndürülemez.
- name/address -> maskeleme (ilk harf + ***).
- email        -> yerel kısmın ilk harfi + ***@***.<tld>.
- phone        -> son 2 hane hariç maskeleme.
- national_id  -> son 2 hane hariç maskeleme.
- iban/card    -> son 4 hane hariç maskeleme.
- quasi (yaş, cinsiyet, konum, doğum tarihi) -> olduğu gibi bırakılır ve
  raporlanır; genelleştirme sentetik veri üretim aşamasında ele alınacak.
"""

import hashlib

import pandas as pd

from app.services.detection import QUASI_CATEGORIES

_HASH_LENGTH = 12


def _hash_value(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:_HASH_LENGTH]


def _mask_text(value: object) -> str:
    text = str(value).strip()
    return f"{text[0]}***" if text else "***"


def _mask_email(value: object) -> str:
    text = str(value).strip()
    local, _, domain = text.partition("@")
    if not domain:
        return "***"
    tld = domain.rsplit(".", 1)[-1]
    first = local[0] if local else "*"
    return f"{first}***@***.{tld}"


def _mask_keep_last(value: object, keep: int) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return "***"
    return "*" * max(len(digits) - keep, 3) + digits[-keep:]


_STRATEGIES: dict[str, tuple[str, object]] = {
    "id": ("hashed", _hash_value),
    "name": ("masked", _mask_text),
    "address": ("masked", _mask_text),
    "email": ("masked", _mask_email),
    "phone": ("masked", lambda v: _mask_keep_last(v, keep=2)),
    "national_id": ("masked", lambda v: _mask_keep_last(v, keep=2)),
    "iban": ("masked", lambda v: _mask_keep_last(v, keep=4)),
    "card_number": ("masked", lambda v: _mask_keep_last(v, keep=4)),
}


def anonymize_dataframe(
    df: pd.DataFrame, detections: list[dict]
) -> tuple[pd.DataFrame, list[dict]]:
    """Tespit sonuçlarına göre kolonları anonimleştirir.

    Orijinal df değiştirilmez; (anonim df, uygulanan aksiyon listesi) döner.
    Aksiyon kaydı: column, category, action (hashed|masked|kept).
    """
    result = df.copy()
    actions: list[dict] = []

    for detection in detections:
        column = detection["column"]
        category = detection["category"]

        if category in QUASI_CATEGORIES:
            action = "kept"
        else:
            action, transform = _STRATEGIES[category]
            mask = result[column].notna()
            result[column] = result[column].astype(object)
            result.loc[mask, column] = result.loc[mask, column].map(transform)

        actions.append({"column": column, "category": category, "action": action})

    return result, actions
