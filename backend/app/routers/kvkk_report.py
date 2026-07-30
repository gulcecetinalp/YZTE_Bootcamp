"""KVKK Risk Raporu endpoint'i.

SCRUM-25 (Task 5): kvkk_agent.py'deki 3 adımlı ajanı (kolon analizi ->
risk skorlama -> LLM rapor) bir HTTP endpoint'ine bağlar.

file_id olarak ORİJİNAL upload dosyasının kimliği alınır (anonymized_file_id
değil). Sebebi: ajan hem detections+actions'a hem de anonimleştirilmiş
DataFrame'e (veri kalitesi taraması için) ihtiyaç duyuyor; bunlar hiçbir
yerde diske kaydedilmediği için, /api/anonymize/{id} ile aynı şekilde
orijinal CSV üzerinden tespit+anonimleştirme burada yeniden çalıştırılıyor.
detect_sensitive_columns ve anonymize_dataframe deterministik olduğundan
(rastgelelik yok) bu tekrar hesaplama pahalı değil ve /api/anonymize'daki
sonuçla birebir aynı çıktıyı verir.
"""

import logging
import os

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.services.anonymization import anonymize_dataframe
from app.services.detection import detect_sensitive_columns
from app.services.kvkk_agent import NarrativeLLM, run_kvkk_agent
from app.storage import csv_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["kvkk-report"])

# Kota testlerimizde bu hesapta 0 çıkan gemini-2.0-flash yerine bunu kullandık.
_MODEL_NAME = "gemini-flash-latest"


def _build_llm() -> NarrativeLLM | None:
    """GOOGLE_API_KEY .env'de tanımlıysa gerçek bir Gemini istemcisi döner.

    Anahtar yoksa ya da langchain-google-genai kurulu değilse None döner -
    bu durumda kvkk_agent.py zaten kural tabanlı şablona düşüyor, endpoint
    çökmüyor.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.info("GOOGLE_API_KEY tanımlı değil, KVKK raporu kural tabanlı üretilecek.")
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=_MODEL_NAME, google_api_key=api_key, temperature=0.2)
    except Exception as exc:  # noqa: BLE001 - LLM kurulamazsa fallback'e düş
        logger.warning("Gemini istemcisi oluşturulamadı, kural tabanlı rapora düşülüyor: %s", exc)
        return None


@router.post("/kvkk-report/{file_id}")
def generate_kvkk_report(file_id: str):
    """Orijinal CSV üzerinden çok adımlı KVKK risk raporu üretir.

    - **file_id**: `/api/upload`'dan dönen orijinal dosya kimliği.

    Ajan üç adımda çalışır: kolon analizi (saf Python) -> risk skorlama
    (deterministik) -> rapor yazımı (LLM varsa Gemini, yoksa şablon).
    Yanıttaki `agent_steps` bu üç adımı gösterir.
    """
    source = csv_path(file_id)
    if not source.is_file():
        raise HTTPException(
            status_code=404,
            detail="Bu file_id ile yüklenmiş bir dosya bulunamadı.",
        )

    try:
        df = pd.read_csv(source)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Kayıtlı dosya geçerli bir CSV olarak okunamadı.",
        )

    detections = detect_sensitive_columns(df)
    anonymized_df, actions = anonymize_dataframe(df, detections)

    llm = _build_llm()
    return run_kvkk_agent(file_id, detections, actions, anonymized_df, llm=llm)
