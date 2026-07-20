from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import anonymize, health, synthetic, upload

app = FastAPI(
    title="AegisAI API",
    description="CSV veri setlerinde hassas veri tespiti, anonimleştirme ve sentetik veri üretimi platformu",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(anonymize.router)
app.include_router(synthetic.router)
