import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AegisAI",
  description:
    "Detect and anonymize sensitive data in CSV datasets, generate privacy-safe synthetic data and KVKK risk reports.",
};

const navItems = [
  { label: "Dashboard", active: true },
  { label: "Anonymize", active: false },
  { label: "Generate", active: false },
  { label: "Reports", active: false },
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
              {navItems.map((item) => (
                <span
                  key={item.label}
                  className={
                    item.active
                      ? "font-medium text-white"
                      : "cursor-not-allowed text-neutral-500"
                  }
                  title={item.active ? undefined : "Coming in a later sprint"}
                >
                  {item.label}
                </span>
              ))}
            </nav>
            <span className="rounded-full bg-emerald-500 px-4 py-1.5 text-sm font-medium text-emerald-950">
              Start Project
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
