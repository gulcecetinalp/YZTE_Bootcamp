"""Task 6-7 duman testi: tespit + anonimleştirme fonksiyonlarını doğrular.

Çalıştırma (backend/ içinden): .venv/bin/python scripts/smoke_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.services.anonymization import anonymize_dataframe
from app.services.detection import detect_sensitive_columns

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    status = "OK " if condition else "FAIL"
    print(f"[{status}] {message}")
    if not condition:
        failures.append(message)


# --- 1. Gerçek veri seti: Bank Customer Churn ---
# Yol öncelik sırası: komut satırı argümanı > repo kökü > ~/Downloads
_candidates = [
    Path(__file__).resolve().parents[2] / "Customer-Churn-Records.csv",
    Path.home() / "Downloads" / "Customer-Churn-Records.csv",
]
if len(sys.argv) > 1:
    _candidates.insert(0, Path(sys.argv[1]))
churn_csv = next((p for p in _candidates if p.is_file()), None)
if churn_csv is None:
    print("Customer-Churn-Records.csv bulunamadi; yolu argüman olarak verin.")
    sys.exit(1)
print(f"Veri seti: {churn_csv}")
df = pd.read_csv(churn_csv)
detections = detect_sensitive_columns(df)
by_column = {d["column"]: d for d in detections}

print("--- Churn veri seti tespitleri ---")
for d in detections:
    print(f"  {d['column']}: {d['category']} ({d['sensitivity']}, {d['detected_by']})")

check(by_column.get("CustomerId", {}).get("category") == "id", "CustomerId -> id")
check(by_column.get("Surname", {}).get("category") == "name", "Surname -> name")
check(by_column.get("Geography", {}).get("sensitivity") == "quasi", "Geography -> quasi")
check(by_column.get("Gender", {}).get("sensitivity") == "quasi", "Gender -> quasi")
check(by_column.get("Age", {}).get("sensitivity") == "quasi", "Age -> quasi")
check("CreditScore" not in by_column, "CreditScore tespit edilmedi")
check("Card Type" not in by_column, "Card Type tespit edilmedi (yanlis pozitif yok)")

anon, actions = anonymize_dataframe(df, detections)
action_by_column = {a["column"]: a["action"] for a in actions}

check(action_by_column.get("CustomerId") == "hashed", "CustomerId hash'lendi")
check(action_by_column.get("Surname") == "masked", "Surname maskelendi")
check(action_by_column.get("Age") == "kept", "Age (quasi) oldugu gibi birakildi")
check(
    (anon["CustomerId"].astype(str) != df["CustomerId"].astype(str)).all(),
    "CustomerId'de ham numara kalmadi",
)
check(
    anon["Surname"].dropna().astype(str).str.endswith("***").all(),
    "Tum soyadlar '<ilk harf>***' formatinda",
)
check(anon["Age"].equals(df["Age"]), "Age degismedi")
check(df["Surname"].iloc[0] != anon["Surname"].iloc[0], "Orijinal df degismedi (kopya)")

print("\n--- Ornek (ilk 3 satir) ---")
cols = [a["column"] for a in actions]
print("Once :", df[cols].head(3).to_dict(orient="records"))
print("Sonra:", anon[cols].head(3).to_dict(orient="records"))

# --- 2. Sentetik ornek: icerik regex'i (kolon adi bilgi vermiyor) ---
tricky = pd.DataFrame(
    {
        "col_a": ["ali@example.com", "veli@mail.co", "ayse.k@firma.com.tr"],
        "col_b": ["12345678950", "98765432110", "45678912350"],
        "col_c": ["0532 123 45 67", "+90 212 555 44 33", "0212-333-22-11"],
        "col_d": ["merhaba", "dunya", "test"],
    }
)
tricky_det = {d["column"]: d for d in detect_sensitive_columns(tricky)}

print("\n--- Icerik regex tespitleri ---")
for d in tricky_det.values():
    print(f"  {d['column']}: {d['category']} (ratio={d['match_ratio']})")

check(tricky_det.get("col_a", {}).get("category") == "email", "icerikten e-posta tespiti")
check(tricky_det.get("col_b", {}).get("category") == "national_id", "icerikten TCKN tespiti")
check(tricky_det.get("col_c", {}).get("category") == "phone", "icerikten telefon tespiti")
check("col_d" not in tricky_det, "duz metin kolonu tespit edilmedi")

tricky_anon, _ = anonymize_dataframe(tricky, list(tricky_det.values()))
check(tricky_anon["col_a"].iloc[0] == "a***@***.com", "e-posta maskesi: a***@***.com")
check(tricky_anon["col_b"].iloc[0].endswith("50"), "TCKN son 2 hane korundu")
check("*" in tricky_anon["col_c"].iloc[0], "telefon maskelendi")

print()
if failures:
    print(f"SONUC: {len(failures)} kontrol BASARISIZ")
    sys.exit(1)
print("SONUC: tum kontroller gecti")
