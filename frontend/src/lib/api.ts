const API_PORT = "8001";

function getApiUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }

  if (typeof window === "undefined") {
    return `http://localhost:${API_PORT}`;
  }

  return `${window.location.protocol}//${window.location.hostname}:${API_PORT}`;
}

export interface ColumnInfo {
  name: string;
  dtype: string;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  num_rows: number;
  num_columns: number;
  columns: ColumnInfo[];
  preview: Record<string, string | number | boolean | null>[];
}

export interface Detection {
  column: string;
  category: string;
  sensitivity: "direct" | "quasi";
  detected_by: string;
  match_ratio: number | null;
}

export interface AnonymizeAction {
  column: string;
  category: string;
  action: "hashed" | "masked" | "kept";
}

export interface AnonymizeResponse {
  file_id: string;
  anonymized_file_id: string;
  num_rows: number;
  num_columns: number;
  detections: Detection[];
  actions: AnonymizeAction[];
  preview: Record<string, string | number | boolean | null>[];
}

export async function uploadCsv(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${getApiUrl()}/api/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    let detail = `Upload failed (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // response body is not JSON; keep the generic message
    }
    throw new Error(detail);
  }

  return res.json();
}

// backend synthetic_faker._compute_stats bize kolon bazlı böyle bir özet dönüyor
export interface NumericStat {
  mean: number;
  std: number;
  min: number;
  max: number;
}

export interface CategoricalStat {
  unique: number;
  top: string | null;
  top_freq: number | null;
}

export interface ColumnStat {
  dtype: string;
  // sayısal kolonda NumericStat, metin kolonunda CategoricalStat geliyor
  original?: NumericStat | CategoricalStat;
  synthetic?: NumericStat | CategoricalStat;
  // sadece sayısal kolonda gelir
  similarity?: number | null;
}

export interface SyntheticResponse {
  file_id: string;
  synthetic_file_id: string;
  method_used: string;
  // CTGAN patlayıp Faker'a düştüyse sebebi burada gelir, yoksa null
  ctgan_fallback_reason: string | null;
  num_rows: number;
  num_columns: number;
  // kolon adı -> istatistik özeti (orijinal vs sentetik karşılaştırması)
  stats: Record<string, ColumnStat>;
  // grafik anahtarı -> base64 PNG (correlation, dist__<col>, count__<col>)
  charts?: Record<string, string>;
  preview: Record<string, string | number | boolean | null>[];
}

export async function synthesizeCsv(
  fileId: string,
  method: "auto" | "ctgan" | "faker" = "auto",
): Promise<SyntheticResponse> {
  // method'u query string olarak gönderiyoruz. auto = önce CTGAN, olmazsa Faker.
  const res = await fetch(
    `${getApiUrl()}/api/synthetic/${fileId}?method=${method}`,
    { method: "POST" },
  );

  if (!res.ok) {
    let detail = `Sentetik veri üretimi başarısız (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // gövde JSON değilse genel mesajı kullan
    }
    throw new Error(detail);
  }

  return res.json();
}

export async function anonymizeCsv(fileId: string): Promise<AnonymizeResponse> {
  const res = await fetch(`${getApiUrl()}/api/anonymize/${fileId}`, {
    method: "POST",
  });

  if (!res.ok) {
    let detail = `Anonymization failed (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // response body is not JSON; keep the generic message
    }
    throw new Error(detail);
  }

  return res.json();
}
