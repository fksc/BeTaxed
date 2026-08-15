const DEFAULT_API_URL = "http://localhost:8080";

export function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || DEFAULT_API_URL;
}
