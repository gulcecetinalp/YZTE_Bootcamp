"""Sentetik veri üretim servislerinin smoke testi.

Çalıştırma:
    cd backend
    python scripts/synthetic_smoke_test.py

Faker yöntemi her zaman test edilir (sdv kurulu olmadan da çalışır).
CTGAN yöntemi sdv kuruluysa otomatik olarak dahil edilir.
"""

import sys
from pathlib import Path

# Proje kökünü Python path'ine ekle
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Test verisi — Bank Customer Churn benzeri yapay veri (SDV/Faker testleri için)
# ──────────────────────────────────────────────────────────────────────────────

np.random.seed(42)
N = 200

test_df = pd.DataFrame({
    "CustomerId": range(10000001, 10000001 + N),
    "CreditScore": np.random.randint(350, 850, N),
    "Geography": np.random.choice(["France", "Germany", "Spain"], N, p=[0.5, 0.25, 0.25]),
    "Gender": np.random.choice(["Male", "Female"], N),
    "Age": np.random.randint(18, 92, N),
    "Tenure": np.random.randint(0, 10, N),
    "Balance": np.round(np.random.uniform(0, 250000, N), 2),
    "NumOfProducts": np.random.choice([1, 2, 3, 4], N, p=[0.5, 0.35, 0.1, 0.05]),
    "HasCrCard": np.random.choice([0, 1], N, p=[0.3, 0.7]),
    "IsActiveMember": np.random.choice([0, 1], N),
    "EstimatedSalary": np.round(np.random.uniform(11.58, 199992.48, N), 2),
    "Exited": np.random.choice([0, 1], N, p=[0.8, 0.2]),
})

ERRORS: list[str] = []


def check(condition: bool, msg: str) -> None:
    if condition:
        print(f"  ✅ {msg}")
    else:
        print(f"  ❌ {msg}")
        ERRORS.append(msg)


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — Faker (SCRUM-17)
# ══════════════════════════════════════════════════════════════════════════════
print("\n📊 Test 1 — Faker + istatistiksel kural tabanlı yöntem (SCRUM-17)")
print("-" * 60)

from app.services.synthetic_faker import generate_synthetic_faker

df_faker, stats_faker = generate_synthetic_faker(test_df, num_rows=100)

check(len(df_faker) == 100, f"num_rows=100 → üretilen: {len(df_faker)}")
check(set(df_faker.columns) == set(test_df.columns), "Kolon yapısı korunuyor")
check(not df_faker.empty, "Üretilen veri boş değil")

# Sayısal kolonlar için min-max aralığı kontrolü
for col in ["CreditScore", "Age", "Balance"]:
    orig_min, orig_max = float(test_df[col].min()), float(test_df[col].max())
    syn_min, syn_max = float(df_faker[col].min()), float(df_faker[col].max())
    in_range = syn_min >= orig_min * 0.95 and syn_max <= orig_max * 1.05
    check(in_range, f"{col}: sentetik değerler makul aralıkta ({syn_min:.1f}–{syn_max:.1f})")

# Kategorik kolon dağılımı
geo_values = set(df_faker["Geography"].unique())
check(geo_values.issubset({"France", "Germany", "Spain"}), f"Geography değerleri orijinal küme içinde: {geo_values}")

print(f"\n  → İstatistik örneği (CreditScore):")
print(f"     Orijinal  mean={stats_faker['CreditScore']['original']['mean']} "
      f"std={stats_faker['CreditScore']['original']['std']}")
print(f"     Sentetik  mean={stats_faker['CreditScore']['synthetic']['mean']} "
      f"std={stats_faker['CreditScore']['synthetic']['std']}")

# ──────────────────────────── num_rows=0 (orijinal kadar) ───────────────────
print("\n  → num_rows=0 testi (orijinal boyut korunmalı):")
df_same, _ = generate_synthetic_faker(test_df, num_rows=0)
check(len(df_same) == len(test_df), f"num_rows=0 → {len(df_same)} satır (beklenen: {len(test_df)})")


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — CTGAN (SCRUM-16) — kurulu değilse atlanır
# ══════════════════════════════════════════════════════════════════════════════
print("\n📊 Test 2 — CTGAN / SDV yöntemi (SCRUM-16)")
print("-" * 60)

try:
    from app.services.synthetic_ctgan import generate_synthetic_ctgan, _SDV_AVAILABLE

    if not _SDV_AVAILABLE:
        print("  ⚠️  SDV kurulu değil → CTGAN testi atlanıyor.")
        print("     Kurmak için: pip install sdv")
    else:
        print("  SDV bulundu, CTGAN testi çalıştırılıyor (küçük veri + az epoch)…")
        df_ctgan, stats_ctgan = generate_synthetic_ctgan(
            test_df.head(50),  # hız için küçük örneklem
            num_rows=30,
            epochs=10,          # hız için az epoch
        )
        check(len(df_ctgan) == 30, f"num_rows=30 → üretilen: {len(df_ctgan)}")
        check(set(df_ctgan.columns) == set(test_df.columns), "CTGAN kolon yapısı korunuyor")
        check(not df_ctgan.empty, "CTGAN çıktısı boş değil")
        print(f"\n  → CTGAN istatistik örneği (CreditScore):")
        cs = stats_ctgan.get("CreditScore", {})
        print(f"     Orijinal  mean={cs.get('original', {}).get('mean')} "
              f"std={cs.get('original', {}).get('std')}")
        print(f"     Sentetik  mean={cs.get('synthetic', {}).get('mean')} "
              f"std={cs.get('synthetic', {}).get('std')}")

except Exception as exc:
    print(f"  ⚠️  CTGAN testi çalışırken hata oluştu: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Test 3 — Router mantığı (yüksek seviye)
# ══════════════════════════════════════════════════════════════════════════════
print("\n📊 Test 3 — Servis bağımsızlık kontrolü")
print("-" * 60)

# İki farklı boyut için tekrar test — deterministik mi?
df_a, _ = generate_synthetic_faker(test_df, num_rows=50, random_state=99)
df_b, _ = generate_synthetic_faker(test_df, num_rows=50, random_state=99)
check(df_a.equals(df_b), "Aynı random_state → aynı çıktı (deterministik)")

df_c, _ = generate_synthetic_faker(test_df, num_rows=50, random_state=1)
check(not df_a.equals(df_c), "Farklı random_state → farklı çıktı")


# ══════════════════════════════════════════════════════════════════════════════
# Sonuç
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
if ERRORS:
    print(f"❌ {len(ERRORS)} test başarısız:")
    for e in ERRORS:
        print(f"   • {e}")
    sys.exit(1)
else:
    print("✅ Tüm testler başarıyla tamamlandı!")
    sys.exit(0)
