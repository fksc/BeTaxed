import { getApiUrl } from "@/lib/api/client";
import { ApiError, HEADER_INTAKE_SESSION, type IntakeOut } from "@/lib/api/types";

type AuthOpts = {
  sessionToken?: string | null;
  idToken?: string | null;
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

function headers(opts: AuthOpts, extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  if (opts.idToken) {
    h.set("Authorization", `Bearer ${opts.idToken}`);
  }
  if (opts.sessionToken) {
    h.set(HEADER_INTAKE_SESSION, opts.sessionToken);
  }
  return h;
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  opts: AuthOpts,
): Promise<T> {
  const response = await fetch(`${getApiUrl()}${path}`, {
    ...init,
    headers: headers(opts, init.headers),
  });
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  return (await response.json()) as T;
}

export async function createIntake(opts: AuthOpts): Promise<IntakeOut> {
  return requestJson<IntakeOut>(
    "/v1/intakes",
    { method: "POST" },
    opts,
  );
}

export async function getIntake(
  intakeId: string,
  opts: AuthOpts,
): Promise<IntakeOut> {
  return requestJson<IntakeOut>(`/v1/intakes/${intakeId}`, { method: "GET" }, opts);
}

export async function uploadSsFiles(
  intakeId: string,
  files: File[],
  periodYearMonth: string,
  opts: AuthOpts,
): Promise<IntakeOut> {
  const body = new FormData();
  body.set("period_year_month", periodYearMonth);
  for (const file of files) {
    body.append("files", file);
  }
  return requestJson<IntakeOut>(
    `/v1/intakes/${intakeId}/uploads`,
    { method: "POST", body },
    opts,
  );
}

export async function convertIntake(
  intakeId: string,
  legalName: string,
  tradingName: string | null,
  opts: AuthOpts,
): Promise<IntakeOut> {
  return requestJson<IntakeOut>(
    `/v1/intakes/${intakeId}/convert`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        legal_name: legalName,
        trading_name: tradingName || null,
      }),
    },
    opts,
  );
}

export async function declineIntake(
  intakeId: string,
  opts: AuthOpts,
): Promise<IntakeOut> {
  return requestJson<IntakeOut>(
    `/v1/intakes/${intakeId}/decline`,
    { method: "POST" },
    opts,
  );
}
