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
uvicorn app.main:app --reload --port 8001
```

- API dokümantasyonu: http://localhost:8001/docs
- Health check: `GET /health`
- CSV yükleme: `POST /api/upload` (multipart form, alan adı: `file`)
- Anonimleştirme: `POST /api/anonymize/{file_id}` — hassas kolonları tespit eder (kolon adı analizi + içerik regex'i), maskeleyip/hash'leyip anonim kopyayı yeni bir `file_id` ile kaydeder; tespit ve aksiyon raporunu döner.

Yüklenen CSV'ler `uploads/` klasörüne `{file_id}.csv` olarak kaydedilir; sonraki adımlar (sentetik veri üretimi) bu `file_id` üzerinden çalışacak.

Hassas veri tespiti şimdilik regex + kolon adı analiziyle çalışır (README'deki mimarinin ilk iki yöntemi); Presidio/SpaCy entegrasyonu sonraki iterasyona bırakıldı.
