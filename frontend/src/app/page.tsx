"use client";

import { useRef, useState } from "react";
import { uploadCsv, type UploadResponse } from "@/lib/api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResponse | null>(null);

  function selectFile(selected: File | null) {
    setError(null);
    setResult(null);
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Only .csv files are supported.");
      return;
    }
    setFile(selected);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    selectFile(e.dataTransfer.files?.[0] ?? null);
  }

  async function handleUpload() {
    if (!file || uploading) return;
    setUploading(true);
    setError(null);
    try {
      setResult(await uploadCsv(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
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
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
            dragActive
              ? "border-emerald-400 bg-emerald-500/10"
              : "border-neutral-700 hover:border-emerald-600"
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
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
          />
        </div>

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
    </div>
  );
}
