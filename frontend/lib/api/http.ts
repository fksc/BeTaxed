import { getApiUrl } from "@/lib/api/client";
import { ApiError } from "@/lib/api/types";

export type AuthOpts = {
  idToken?: string | null;
  companyId?: string | null;
};

async function parseError(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof (body as { detail: unknown }).detail === "string"
    ) {
      return (body as { detail: string }).detail;
    }
  } catch {
    /* ignore */
  }
  return response.statusText || `HTTP ${response.status}`;
}

export function authHeaders(opts: AuthOpts, extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  if (opts.idToken) {
    h.set("Authorization", `Bearer ${opts.idToken}`);
  }
  if (opts.companyId) {
    h.set("X-Company-Id", opts.companyId);
  }
  return h;
}

export async function apiJson<T>(
  path: string,
  init: RequestInit,
  opts: AuthOpts,
): Promise<T> {
  const response = await fetch(`${getApiUrl()}${path}`, {
    ...init,
    headers: authHeaders(opts, init.headers),
  });
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
