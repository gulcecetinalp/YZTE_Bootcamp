import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routers import anonymize, health, synthetic, upload

# Local geliştirmede frontend hep bu adreslerde açılıyor. Deploy edince
# domain değişeceği için origin'leri koda gömmek yerine env'den okuyoruz.
_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://[::1]:3000",
]


def get_cors_origins() -> list[str]:
    # AEGISAI_CORS_ORIGINS="https://siteadi.vercel.app,https://..." şeklinde
    # virgülle ayrılmış verilebilir. Yoksa varsayılan local listesi kullanılır.
    raw = os.getenv("AEGISAI_CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return _DEFAULT_ORIGINS


app = FastAPI(
    title="AegisAI API",
    description="CSV veri setlerinde hassas veri tespiti, anonimleştirme ve sentetik veri üretimi platformu",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    # Her yanıta temel güvenlik başlıkları ekliyoruz. Bunlar tarayıcıya
    # "içerik tipini tahmin etme", "bu sayfayı iframe'e gömme" gibi talimatlar
    # veriyor. Küçük ama işe yarayan bir güvenlik adımı.
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(anonymize.router)
app.include_router(synthetic.router)
