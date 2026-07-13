# AegisAI Frontend (Next.js + Tailwind CSS)

## Kurulum

```bash
cd frontend
npm install
```

## Çalıştırma

```bash
npm run dev
```

Uygulama http://localhost:3000 adresinde açılır. CSV yükleme akışının çalışması için backend'in http://localhost:8000 üzerinde ayakta olması gerekir (bkz. `backend/README.md`).

Backend farklı bir adresteyse `frontend/.env.local` dosyasına `NEXT_PUBLIC_API_URL=<adres>` yazın; varsayılan `http://localhost:8000`.
