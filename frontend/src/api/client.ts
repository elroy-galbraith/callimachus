// Thin fetch wrapper around the FastAPI surface.
//
// We deliberately keep this small — no runtime client library. Types come
// from `openapi-typescript` (regenerate with `npm run gen:api`); URLs and
// request bodies stay readable inline at the call site.

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
    public path: string,
  ) {
    super(`API ${status} on ${path}: ${typeof body === "string" ? body : JSON.stringify(body)}`);
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const finalInit: RequestInit = {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(headers ?? {}),
    },
    ...(json !== undefined ? { body: JSON.stringify(json) } : {}),
  };

  const res = await fetch(`${BASE}${path}`, finalInit);
  if (!res.ok) {
    let body: unknown = await res.text();
    try {
      body = JSON.parse(body as string);
    } catch {
      /* keep text */
    }
    throw new ApiError(res.status, body, path);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

/**
 * Pull a user-readable detail out of an unknown thrown value. FastAPI's
 * default error shape is ``{detail: string | object}``; anything else
 * falls back to the raw body or the JS error message.
 */
export function extractErrorDetail(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in e.body) {
      return String((e.body as { detail: unknown }).detail);
    }
    return String(e.body);
  }
  return (e as Error).message;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "POST", json }),
  patch: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "PATCH", json }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, files: FileList | File[]) => {
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    return request<T>(path, { method: "POST", body: fd });
  },
};
