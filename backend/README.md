# AegisAI Backend (FastAPI)

## Kurulum

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Çalıştırma

```bash
uvicorn app.main:app --reload --port 8000
```

- API dokümantasyonu: http://localhost:8000/docs
- Health check: `GET /health`
- CSV yükleme: `POST /api/upload` (multipart form, alan adı: `file`)

Yüklenen CSV'ler `uploads/` klasörüne `{file_id}.csv` olarak kaydedilir; sonraki adımlar (anonimleştirme, sentetik veri) bu `file_id` üzerinden çalışacak.
