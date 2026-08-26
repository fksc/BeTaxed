import { apiJson, type AuthOpts } from "@/lib/api/http";
import type {
  BenefitCaseOut,
  CertificateOut,
  CompanyApplicationOut,
  HeadcountMonthOut,
  MeOut,
  MismatchFlag,
  NotificationList,
  PersonOut,
  SsBatchOut,
} from "@/lib/api/workspace";

export async function getMe(opts: AuthOpts): Promise<MeOut> {
  return apiJson<MeOut>("/v1/me", { method: "GET" }, opts);
}

export async function listPeople(opts: AuthOpts): Promise<PersonOut[]> {
  return apiJson<PersonOut[]>("/v1/people", { method: "GET" }, opts);
}

export async function patchPersonStatus(
  employeeId: string,
  body: {
    status: "ACTIVE" | "ON_LEAVE" | "TERMINATED";
    leave_type?: "PARENTAL" | "SICKNESS" | "UNPAID" | "OTHER";
    effective_on?: string;
  },
  opts: AuthOpts,
): Promise<PersonOut> {
  return apiJson<PersonOut>(
    `/v1/people/${employeeId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    opts,
  );
}

export async function uploadPersonContract(
  employeeId: string,
  file: File,
  opts: AuthOpts,
): Promise<{ id: string; review_status: string }> {
  const body = new FormData();
  body.set("file", file);
  return apiJson(`/v1/people/${employeeId}/contracts`, { method: "POST", body }, opts);
}

export async function listNotifications(opts: AuthOpts): Promise<NotificationList> {
  return apiJson<NotificationList>("/v1/notifications", { method: "GET" }, opts);
}

export async function markNotificationRead(
  notificationId: string,
  opts: AuthOpts,
): Promise<void> {
  await apiJson(`/v1/notifications/${notificationId}/read`, { method: "POST" }, opts);
}

export async function markAllNotificationsRead(opts: AuthOpts): Promise<void> {
  await apiJson("/v1/notifications/read-all", { method: "POST" }, opts);
}

export async function listContractFlags(opts: AuthOpts): Promise<MismatchFlag[]> {
  return apiJson<MismatchFlag[]>("/v1/ops/contract-flags", { method: "GET" }, opts);
}

export async function applyContractDocument(
  documentId: string,
  opts: AuthOpts,
): Promise<void> {
  await apiJson(
    `/v1/ops/employment-documents/${documentId}/apply`,
    { method: "POST" },
    opts,
  );
}

export async function listSsBatches(opts: AuthOpts): Promise<SsBatchOut[]> {
  return apiJson<SsBatchOut[]>("/v1/ss-batches", { method: "GET" }, opts);
}

export async function uploadCompanySs(
  files: File[],
  periodYearMonth: string,
  opts: AuthOpts,
): Promise<SsBatchOut> {
  const body = new FormData();
  body.set("period_year_month", periodYearMonth);
  for (const file of files) {
    body.append("files", file);
  }
  return apiJson<SsBatchOut>("/v1/ss-batches", { method: "POST", body }, opts);
}

export async function listHeadcountMonths(opts: AuthOpts): Promise<HeadcountMonthOut[]> {
  return apiJson<HeadcountMonthOut[]>("/v1/headcount-months", { method: "GET" }, opts);
}

export async function putUserHeadcount(
  yearMonth: string,
  headcount: number,
  opts: AuthOpts,
): Promise<HeadcountMonthOut> {
  return apiJson<HeadcountMonthOut>(
    "/v1/headcount-months",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year_month: yearMonth, headcount }),
    },
    opts,
  );
}

export async function listBenefitCases(opts: AuthOpts): Promise<BenefitCaseOut[]> {
  return apiJson<BenefitCaseOut[]>("/v1/ops/benefit-cases", { method: "GET" }, opts);
}

export async function submitCompanyApplication(
  companyId: string,
  opts: AuthOpts,
): Promise<CompanyApplicationOut> {
  return apiJson<CompanyApplicationOut>(
    `/v1/ops/companies/${companyId}/applications`,
    { method: "POST" },
    opts,
  );
}

export async function listCertificates(opts: AuthOpts): Promise<CertificateOut[]> {
  return apiJson<CertificateOut[]>("/v1/certificates", { method: "GET" }, opts);
}

export async function uploadCertificate(
  kind: "SS_NO_DEBT" | "AT_NO_DEBT",
  issuedOn: string,
  file: File,
  opts: AuthOpts,
): Promise<CertificateOut> {
  const body = new FormData();
  body.set("kind", kind);
  body.set("issued_on", issuedOn);
  body.set("file", file);
  return apiJson<CertificateOut>("/v1/certificates", { method: "POST", body }, opts);
}
