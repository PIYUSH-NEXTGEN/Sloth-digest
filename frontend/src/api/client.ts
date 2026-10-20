import type { components, operations } from "../types";
import type { Digest } from "../types";

// Digest comes from the canonical JSON Schema (contracts/digest.schema.json).
// The openapi.yaml component mirrors it with looser array typing; json2ts
// encodes minItems: 1 as a tuple, so canonical types stay stricter.
export type ConversationInfo = components["schemas"]["ConversationInfo"];
export type Settings = components["schemas"]["Settings"];
export type IngestResult = components["schemas"]["IngestResult"];
export type DigestRunResult = components["schemas"]["DigestRunResult"];
export type Answer = components["schemas"]["Answer"];
export type Health =
  operations["getHealth"]["responses"]["200"]["content"]["application/json"];

const BASE_URL: string =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ??
  "http://localhost:8000";

export class APIError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail || `API error ${status}`);
    this.status = status;
    this.name = "APIError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // non-JSON error body: fall back to statusText
    }
    throw new APIError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

export function listSources(): Promise<{ conversations: ConversationInfo[] }> {
  return request<{ conversations: ConversationInfo[] }>("/sources");
}

export function ingestFile(file: File): Promise<IngestResult> {
  const form = new FormData();
  form.append("file", file);
  return request<IngestResult>("/ingest/file", { method: "POST", body: form });
}

export type DigestRunRequest = {
  since?: string;
  conversation_ids?: string[];
};

export function runDigest(body?: DigestRunRequest): Promise<DigestRunResult> {
  return request<DigestRunResult>("/digest/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

export function getLatestDigest(): Promise<Digest> {
  return request<Digest>("/digest/latest");
}

export function getDigest(digestId: string): Promise<Digest> {
  return request<Digest>(`/digest/${encodeURIComponent(digestId)}`);
}

export function ask(question: string): Promise<Answer> {
  return request<Answer>("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export function getSettings(): Promise<Settings> {
  return request<Settings>("/settings");
}

export function updateSettings(body: Settings): Promise<Settings> {
  return request<Settings>("/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
