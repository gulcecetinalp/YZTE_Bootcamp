export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

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

  const res = await fetch(`${API_URL}/api/upload`, {
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

export async function anonymizeCsv(fileId: string): Promise<AnonymizeResponse> {
  const res = await fetch(`${API_URL}/api/anonymize/${fileId}`, {
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
