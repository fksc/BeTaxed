const DEFAULT_API_URL = "http://localhost:8080";

export function getApiUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim() ?? "";
  if (!raw || raw === "same-origin") {
    return "";
  }
  return raw.replace(/\/$/, "") || DEFAULT_API_URL;
}
