// Fetch wrapper. The session is an httpOnly cookie set by the API (never
// readable by JavaScript). Every failure becomes a plain sentence for a toast.
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "/api";

export class ApiError extends Error {
  status: number;
  detail: any;
  code: string;
  constructor(status: number, message: string, detail: any) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.code = detail?.code || "";
  }
}

function messageOf(status: number, body: any): string {
  const d = body?.detail;
  if (typeof d === "string") return d;
  if (d?.message) return d.errors?.length ? `${d.message} ${d.errors[0]}` : d.message;
  if (status === 0) return "Cannot reach the server. Check your internet connection and try again.";
  if (status >= 500) return "Something went wrong on the server. Please try again in a minute.";
  return "That did not work. Please try again.";
}

let onExpired: (() => void) | null = null;
/** Called once when a signed-in request comes back 401 (session ended). */
export function setExpiredHandler(f: () => void) { onExpired = f; }

export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Requested-With": "samanvay" };
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  let res: Response;
  try {
    res = await fetch(BASE + path, { method: opts.method || (body ? "POST" : "GET"), headers, body, credentials: "include" });
  } catch {
    throw new ApiError(0, messageOf(0, null), null);
  }
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("json") ? await res.json().catch(() => null) : null;
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/")) onExpired?.();
    throw new ApiError(res.status, messageOf(res.status, data), data?.detail);
  }
  return data as T;
}

async function raw(path: string): Promise<Blob> {
  const res = await fetch(BASE + path, { credentials: "include" });
  if (!res.ok) throw new ApiError(res.status, "The file could not be opened.", null);
  return res.blob();
}

export async function download(path: string, filename: string) {
  const url = URL.createObjectURL(await raw(path));
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function blobUrl(path: string): Promise<string> {
  return URL.createObjectURL(await raw(path));
}

export const apiBase = BASE;
