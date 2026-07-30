"""CSV okuma: baştaki sıfırları koruyan tip çıkarımı.

pandas varsayılan olarak tamamen rakamdan oluşan kolonları sayıya çeviriyor.
Bu, kimlik niteliği taşıyan alanlarda sessiz veri kaybına yol açıyordu:

    05551112233       -> 5551112233        (telefonun başındaki 0 uçuyor)
    06100             -> 6100              (posta kodu)
    0489354626550996  -> 489354626550996   (kart numarası)

Türkiye'deki bütün cep telefonu numaraları ve posta kodları 0 ile başladığı
için bu kayıp neredeyse her veri setinde oluşuyordu. Üstelik kayıp
anonimleştirmeden ÖNCE, dosya okunduğu anda gerçekleşiyordu.

Çözüm: her şeyi metin olarak okuyup tip çıkarımını kendimiz yapmak. Baştaki
sıfırı olan bir kolon metin kalır; geri kalanlar eskisi gibi sayıya çevrilir
(istatistik ve grafik üretimi bozulmasın diye).
"""

import pandas as pd

# "0" ve "0.5" gibi değerler baştaki sıfır sayılmaz; "05551112233" sayılır.
_PADDED_NUMBER_PATTERN = r"0\d+"


def _has_padded_numbers(series: pd.Series) -> bool:
    """Kolonda baştaki sıfırla yazılmış en az bir sayı var mı?"""
    values = series.dropna().astype(str).str.strip()
    if values.empty:
        return False
    return bool(values.str.fullmatch(_PADDED_NUMBER_PATTERN).any())


def read_csv(source) -> pd.DataFrame:
    """CSV'yi okur; baştaki sıfırı olan kolonları metin olarak bırakır.

    source: dosya yolu (Path/str) ya da bytes tamponu (BytesIO) olabilir.
    """
    df = pd.read_csv(source, dtype=str)

    for column in df.columns:
        if _has_padded_numbers(df[column]):
            # Kimlik niteliğinde bir alan; sayıya çevirmek veriyi bozar.
            continue

        converted = pd.to_numeric(df[column], errors="coerce")
        # Yalnızca dolu hücrelerin TAMAMI sayıya çevrilebildiyse dönüştür.
        # Aksi halde (ör. "abc", "1.234,5") kolon metin kalır.
        if converted.notna().sum() == df[column].notna().sum():
            df[column] = converted

    return df
