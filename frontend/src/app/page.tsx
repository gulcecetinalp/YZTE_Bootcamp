"use client";

import { useId, useState } from "react";
import {
  uploadCsv,
  anonymizeCsv,
  type UploadResponse,
  type AnonymizeResponse,
} from "@/lib/api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const SENSITIVITY_LABEL: Record<string, string> = {
  direct: "Doğrudan Tanımlayıcı",
  quasi: "Dolaylı Tanımlayıcı",
};

const ACTION_LABEL: Record<string, string> = {
  hashed: "Hash",
  masked: "Maskelendi",
  kept: "Olduğu gibi bırakıldı",
};

const ACTION_COLOR: Record<string, string> = {
  hashed: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  masked: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  kept: "text-neutral-400 bg-neutral-500/10 border-neutral-500/30",
};

const SENSITIVITY_COLOR: Record<string, string> = {
  direct: "text-red-400 bg-red-500/10 border-red-500/30",
  quasi: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
};

export default function Home() {
  const inputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnonymizeResponse | null>(null);

  function selectFile(selected: File | null) {
    setError(null);
    setResult(null);
    setAnalysisResult(null);
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Only .csv files are supported.");
      return;
    }
    setFile(selected);
  }

  function handleDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragActive(false);
    selectFile(e.dataTransfer.files?.[0] ?? null);
  }

  async function handleUpload() {
    if (!file || uploading) return;
    setUploading(true);
    setError(null);
    setAnalysisResult(null);
    try {
      setResult(await uploadCsv(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleAnalyze() {
    if (!result || analyzing) return;
    setAnalyzing(true);
    setError(null);
    try {
      setAnalysisResult(await anonymizeCsv(result.file_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analiz başarısız oldu.");
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="text-center">
        <h1 className="text-3xl font-bold">Upload Your Dataset</h1>
        <p className="mt-2 text-neutral-400">
          Upload a CSV file to start the privacy-safe data pipeline.
        </p>
      </section>

      <section className="rounded-2xl border border-emerald-950/70 bg-[#0e1613] p-6">
        <label
          htmlFor={inputId}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
            dragActive
              ? "border-emerald-400 bg-emerald-500/10"
              : "border-neutral-700 hover:border-emerald-600 focus-within:border-emerald-500"
          }`}
        >
          <span className="text-3xl">📄</span>
          <p className="mt-3 font-medium">
            Drag &amp; drop your CSV file here, or click to browse
          </p>
          <p className="mt-1 text-sm text-neutral-500">
            Only .csv files, up to 20 MB
          </p>
          <input
            id={inputId}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onClick={(e) => {
              e.currentTarget.value = "";
            }}
            onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
          />
        </label>

        {file && (
          <div className="mt-4 flex items-center justify-between rounded-lg bg-[#131d19] px-4 py-3">
            <div>
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-neutral-500">{formatBytes(file.size)}</p>
            </div>
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="rounded-full bg-emerald-500 px-5 py-2 text-sm font-medium text-emerald-950 transition-colors hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        )}

        {error && (
          <p className="mt-4 rounded-lg border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        )}
      </section>

      {result && (
        <section className="grid gap-6 lg:grid-cols-3">
          <div className="rounded-2xl border border-emerald-950/70 bg-[#0e1613] p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Dataset Status</h2>
              <span className="rounded-full border border-emerald-500/50 px-3 py-0.5 text-xs text-emerald-400">
                Active
              </span>
            </div>
            <dl className="mt-6 space-y-5">
              <div>
                <dt className="text-sm text-neutral-500">File</dt>
                <dd className="mt-1 font-medium break-all">{result.filename}</dd>
              </div>
              <div className="flex gap-12">
                <div>
                  <dt className="text-sm text-neutral-500">Rows</dt>
                  <dd className="mt-1 text-2xl font-bold">
                    {result.num_rows.toLocaleString("en-US")}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-neutral-500">Columns</dt>
                  <dd className="mt-1 text-2xl font-bold">{result.num_columns}</dd>
                </div>
              </div>
              <div>
                <dt className="text-sm text-neutral-500">File ID</dt>
                <dd className="mt-1 font-mono text-xs text-neutral-400 break-all">
                  {result.file_id}
                </dd>
              </div>
            </dl>

            {/* Analiz Et butonu */}
            <button
              id="analyze-btn"
              onClick={handleAnalyze}
              disabled={analyzing || !!analysisResult}
              className="mt-6 w-full rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {analyzing
                ? "Analiz ediliyor..."
                : analysisResult
                ? "✓ Analiz Tamamlandı"
                : "Analiz Et & Anonimleştir"}
            </button>
          </div>

          <div className="rounded-2xl border border-emerald-950/70 bg-[#0e1613] p-6 lg:col-span-2">
            <h2 className="text-lg font-semibold">Detected Columns</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {result.columns.map((col) => (
                <span
                  key={col.name}
                  className="rounded-full bg-[#131d19] px-3 py-1 text-sm"
                >
                  {col.name}
                  <span className="ml-2 text-xs text-emerald-400">{col.dtype}</span>
                </span>
              ))}
            </div>

            <h2 className="mt-8 text-lg font-semibold">Preview (first 5 rows)</h2>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-neutral-800 text-neutral-500">
                    {result.columns.map((col) => (
                      <th key={col.name} className="px-3 py-2 font-medium">
                        {col.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.preview.map((row, i) => (
                    <tr key={i} className="border-b border-neutral-900">
                      {result.columns.map((col) => (
                        <td key={col.name} className="px-3 py-2 whitespace-nowrap">
                          {row[col.name] === null ? "—" : String(row[col.name])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* ── Analiz Sonuçları Paneli ── */}
      {analysisResult && (
        <section id="analysis-results" className="space-y-6">
          <h2 className="text-2xl font-bold">
            🔍 Analiz Sonuçları
          </h2>

          {/* Özet kartlar */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl border border-emerald-950/70 bg-[#0e1613] p-5 text-center">
              <p className="text-sm text-neutral-500">Tespit Edilen Hassas Kolon</p>
              <p className="mt-2 text-3xl font-bold text-emerald-400">
                {analysisResult.detections.length}
              </p>
            </div>
            <div className="rounded-2xl border border-red-900/40 bg-[#0e1613] p-5 text-center">
              <p className="text-sm text-neutral-500">Doğrudan Tanımlayıcı</p>
              <p className="mt-2 text-3xl font-bold text-red-400">
                {analysisResult.detections.filter((d) => d.sensitivity === "direct").length}
              </p>
            </div>
            <div className="rounded-2xl border border-yellow-900/40 bg-[#0e1613] p-5 text-center">
              <p className="text-sm text-neutral-500">Dolaylı Tanımlayıcı</p>
              <p className="mt-2 text-3xl font-bold text-yellow-400">
                {analysisResult.detections.filter((d) => d.sensitivity === "quasi").length}
              </p>
            </div>
          </div>

          {/* Tespit tablosu */}
          <div className="rounded-2xl border border-emerald-950/70 bg-[#0e1613] p-6">
            <h3 className="text-lg font-semibold">Tespit Detayları</h3>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-neutral-800 text-neutral-500">
                    <th className="px-3 py-2 font-medium">Kolon</th>
                    <th className="px-3 py-2 font-medium">Kategori</th>
                    <th className="px-3 py-2 font-medium">Duyarlılık</th>
                    <th className="px-3 py-2 font-medium">Tespit Yöntemi</th>
                    <th className="px-3 py-2 font-medium">Uygulanan İşlem</th>
                  </tr>
                </thead>
                <tbody>
                  {analysisResult.detections.map((det) => {
                    const actionObj = analysisResult.actions.find(
                      (a) => a.column === det.column
                    );
                    return (
                      <tr key={det.column} className="border-b border-neutral-900">
                        <td className="px-3 py-2 font-mono text-xs text-emerald-300">
                          {det.column}
                        </td>
                        <td className="px-3 py-2 capitalize">{det.category}</td>
                        <td className="px-3 py-2">
                          <span
                            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                              SENSITIVITY_COLOR[det.sensitivity] ?? ""
                            }`}
                          >
                            {SENSITIVITY_LABEL[det.sensitivity] ?? det.sensitivity}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-neutral-400">
                          {det.detected_by === "column_name"
                            ? "Kolon adı"
                            : "İçerik regex"}
                          {det.match_ratio !== null && (
                            <span className="ml-1 text-xs text-neutral-600">
                              ({(det.match_ratio * 100).toFixed(0)}%)
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {actionObj && (
                            <span
                              className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                                ACTION_COLOR[actionObj.action] ?? ""
                              }`}
                            >
                              {ACTION_LABEL[actionObj.action] ?? actionObj.action}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Anonimleştirilmiş önizleme */}
          <div className="rounded-2xl border border-emerald-950/70 bg-[#0e1613] p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">
                Anonimleştirilmiş Veri Önizlemesi (ilk 5 satır)
              </h3>
              <span className="rounded-full border border-emerald-500/40 px-3 py-0.5 text-xs text-emerald-400">
                ID: {analysisResult.anonymized_file_id.slice(0, 8)}…
              </span>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-neutral-800 text-neutral-500">
                    {Object.keys(analysisResult.preview[0] ?? {}).map((col) => (
                      <th key={col} className="px-3 py-2 font-medium">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {analysisResult.preview.map((row, i) => (
                    <tr key={i} className="border-b border-neutral-900">
                      {Object.entries(row).map(([col, val]) => (
                        <td key={col} className="px-3 py-2 whitespace-nowrap">
                          {val === null ? "—" : String(val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
