import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AegisAI",
  description:
    "CSV veri setlerindeki hassas verileri tespit edip anonimleştiren, gizlilik odaklı sentetik veri ve KVKK risk raporu üreten platform.",
};

const navItems = [
  { label: "Pano", active: true },
  { label: "Anonimleştir", active: false },
  { label: "Üret", active: false },
  { label: "Raporlar", active: false },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // suppressHydrationWarning: tarayıcı eklentileri (ör. Trancy) <html>'e
    // attribute enjekte edip sahte hydration uyarısı üretiyor
    <html lang="tr" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <header className="border-b border-emerald-950/60 bg-[#070d0b]">
          <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
            <div className="flex items-center gap-2">
              {/* Aegis = kalkan; logoyu emoji yerine sade bir SVG ile veriyoruz */}
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
                className="h-5 w-5 text-emerald-400"
              >
                <path d="M12 2 4 5v6.5c0 4.6 3.2 8.9 8 10.5 4.8-1.6 8-5.9 8-10.5V5l-8-3Z" />
              </svg>
              <span className="text-lg font-semibold">
                Aegis<span className="text-emerald-400">AI</span>
              </span>
            </div>
            <nav className="hidden items-center gap-8 text-sm md:flex">
              <a
                href="#upload-section"
                className="text-neutral-300 transition-colors hover:text-white"
              >
                Yükle
              </a>
              <a
                href="#analysis-results"
                className="text-neutral-300 transition-colors hover:text-white"
              >
                Anonimleştir
              </a>
              <a
                href="#synthetic-section"
                className="text-neutral-300 transition-colors hover:text-white"
              >
                Üret
              </a>
              <a
                href="#reports-section"
                className="text-neutral-300 transition-colors hover:text-white"
              >
                Raporlar
              </a>
            </nav>
            <a
              href="#upload-section"
              className="rounded-full bg-emerald-500 px-4 py-1.5 text-sm font-medium text-emerald-950 transition-colors hover:bg-emerald-400"
            >
              Projeye Başla
            </a>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
