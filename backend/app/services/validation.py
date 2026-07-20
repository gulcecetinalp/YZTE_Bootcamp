"""CSV yükleme validasyonu.

SCRUM-28 (yanlış format) ve SCRUM-29 (boş/bozuk/çok büyük dosya) için
yaptığımız kontroller burada toplanıyor. Amaç basit: kullanıcı bize
CSV olmayan / bozuk / kocaman bir dosya atınca kod çirkin bir şekilde
patlamasın, onun yerine düzgün bir hata mesajı dönelim.

Bütün kontroller HTTPException fırlatıyor, yani upload endpoint'i bunları
tek tek yakalamak zorunda değil; FastAPI mesajı direkt kullanıcıya iletiyor.
"""

import io

import pandas as pd
from fastapi import HTTPException, UploadFile

# Kabul ettiğimiz en büyük dosya. Frontend'de de "up to 20 MB" yazıyor,
# ikisi aynı kalsın diye buraya sabit koyduk.
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

# Dosyayı 1 MB'lik parçalar halinde okuyoruz (aşağıda anlattım niye)
_CHUNK_SIZE = 1024 * 1024


def check_extension(filename: str | None) -> None:
    """Dosya adı .csv ile bitiyor mu diye bakar."""
    # not: burada sadece isme bakıyoruz. Adı .csv olup içi bambaşka olan
    # bir dosya gelirse onu da aşağıdaki parse_csv zaten yakalıyor.
    if not filename or not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Sadece .csv uzantılı dosyalar yüklenebilir.",
        )


async def read_within_limit(file: UploadFile) -> bytes:
    """Dosyayı boyut sınırını aşmadan, parça parça okur.

    Eskiden `await file.read()` ile dosyanın tamamını bir kerede belleğe
    alıp ondan sonra boyutuna bakıyorduk. Sorun şu: biri 2 GB'lık dosya
    atarsa reddetmeden önce o 2 GB'ı komple RAM'e yüklemiş oluyorduk.
    Bu yüzden parça parça okuyup, limiti geçtiğimiz anda durup hata dönüyoruz.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:  # dosya bitti
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,  # Payload Too Large
                detail="Dosya boyutu 20 MB sınırını aşıyor.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def parse_csv(contents: bytes) -> pd.DataFrame:
    """Byte'ları pandas DataFrame'e çevirir, olmazsa anlaşılır hata döner."""
    try:
        return pd.read_csv(io.BytesIO(contents))
    except pd.errors.EmptyDataError:
        # dosya tamamen boş (tek satır bile yok)
        raise HTTPException(
            status_code=400,
            detail="Dosya boş görünüyor, içinde okunacak veri yok.",
        )
    except pd.errors.ParserError:
        # satırların kolon sayısı tutmuyor vb. -> bozuk CSV
        raise HTTPException(
            status_code=400,
            detail="CSV yapısı bozuk (satırlardaki kolon sayıları uyuşmuyor olabilir).",
        )
    except Exception:
        # yukarıdakilere girmeyen her şey. pandas'ın kendi mesajı kullanıcı
        # için çok teknik olduğundan sade bir mesaj veriyoruz.
        raise HTTPException(
            status_code=400,
            detail="Dosya geçerli bir CSV olarak okunamadı.",
        )


def validate_dataframe(df: pd.DataFrame) -> None:
    """Parse olmuş DataFrame gerçekten işlenebilir mi diye son kontroller."""
    # hiç kolon yoksa yapacak bir şey yok
    if df.shape[1] == 0:
        raise HTTPException(
            status_code=400,
            detail="CSV'de hiç kolon bulunamadı.",
        )
    # başlık var ama tek satır veri yoksa (mesela sadece header satırı)
    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="CSV'de başlık var ama veri satırı yok.",
        )
