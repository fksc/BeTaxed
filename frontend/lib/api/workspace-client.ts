import { apiJson, type AuthOpts } from "@/lib/api/http";
import type {
  BillingSettingsOut,
  BenefitCaseOut,
  CertificateOut,
  CompanyApplicationOut,
  CompanyInvoiceOut,
  HeadcountMonthOut,
  InviteOut,
  MembersBundleOut,
  MeOut,
  MismatchFlag,
  NotificationList,
  OpsCompanyDetailOut,
  OpsCompanyListOut,
  PersonOut,
  PublicInviteOut,
  SsBatchOut,
  StaffInvoiceOut,
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

export async function listCompanyInvoices(opts: AuthOpts): Promise<CompanyInvoiceOut[]> {
  return apiJson<CompanyInvoiceOut[]>("/v1/invoices", { method: "GET" }, opts);
}

export async function listOpsInvoices(opts: AuthOpts): Promise<StaffInvoiceOut[]> {
  return apiJson<StaffInvoiceOut[]>("/v1/ops/invoices", { method: "GET" }, opts);
}

export async function createDraftInvoice(
  companyId: string,
  yearMonth: string,
  opts: AuthOpts,
): Promise<StaffInvoiceOut> {
  return apiJson<StaffInvoiceOut>(
    `/v1/ops/companies/${companyId}/invoices`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year_month: yearMonth }),
    },
    opts,
  );
}

export async function issueInvoice(invoiceId: string, opts: AuthOpts): Promise<StaffInvoiceOut> {
  return apiJson<StaffInvoiceOut>(
    `/v1/ops/invoices/${invoiceId}/issue`,
    { method: "POST" },
    opts,
  );
}

export async function resolveInvoice(
  invoiceId: string,
  reason: string,
  opts: AuthOpts,
): Promise<StaffInvoiceOut> {
  return apiJson<StaffInvoiceOut>(
    `/v1/ops/invoices/${invoiceId}/resolve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    },
    opts,
  );
}

export async function uploadProforma(
  invoiceId: string,
  file: File,
  opts: AuthOpts,
): Promise<CompanyInvoiceOut> {
  const body = new FormData();
  body.set("file", file);
  return apiJson<CompanyInvoiceOut>(
    `/v1/invoices/${invoiceId}/proforma`,
    { method: "POST", body },
    opts,
  );
}

export async function uploadLegalPdf(
  invoiceId: string,
  file: File,
  fields: {
    legalNumber?: string;
    atcud?: string;
    certifiedExternalId?: string;
    dueOn?: string;
  },
  opts: AuthOpts,
): Promise<CompanyInvoiceOut> {
  const body = new FormData();
  body.set("file", file);
  if (fields.legalNumber) {
    body.set("legal_invoice_number", fields.legalNumber);
  }
  if (fields.atcud) {
    body.set("atcud", fields.atcud);
  }
  if (fields.certifiedExternalId) {
    body.set("certified_external_id", fields.certifiedExternalId);
  }
  if (fields.dueOn) {
    body.set("due_on", fields.dueOn);
  }
  return apiJson<CompanyInvoiceOut>(
    `/v1/invoices/${invoiceId}/legal-pdf`,
    { method: "POST", body },
    opts,
  );
}

export async function setCompanyInvoicing(
  companyId: string,
  invoicingMethod: string,
  certifiedVendorName: string,
  opts: AuthOpts,
): Promise<{ invoicing_method: string | null; certified_vendor_name: string | null }> {
  return apiJson(
    `/v1/ops/companies/${companyId}/invoicing`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        invoicing_method: invoicingMethod,
        certified_vendor_name: certifiedVendorName || null,
      }),
    },
    opts,
  );
}

export async function getBillingSettings(opts: AuthOpts): Promise<BillingSettingsOut> {
  return apiJson<BillingSettingsOut>("/v1/billing", { method: "GET" }, opts);
}

export async function startSepaCheckout(opts: AuthOpts): Promise<{ url: string }> {
  return apiJson<{ url: string }>("/v1/invoices/sepa-checkout", { method: "POST" }, opts);
}

export async function collectSepa(
  invoiceId: string,
  opts: AuthOpts,
): Promise<CompanyInvoiceOut> {
  return apiJson<CompanyInvoiceOut>(
    `/v1/invoices/${invoiceId}/sepa-collect`,
    { method: "POST" },
    opts,
  );
}

export async function collectOpsInvoice(
  invoiceId: string,
  opts: AuthOpts,
): Promise<StaffInvoiceOut> {
  return apiJson<StaffInvoiceOut>(
    `/v1/ops/invoices/${invoiceId}/collect`,
    { method: "POST" },
    opts,
  );
}

export async function listOpsCompanies(opts: AuthOpts): Promise<OpsCompanyListOut[]> {
  return apiJson<OpsCompanyListOut[]>("/v1/ops/companies", { method: "GET" }, opts);
}

export async function getOpsCompany(
  companyId: string,
  opts: AuthOpts,
): Promise<OpsCompanyDetailOut> {
  return apiJson<OpsCompanyDetailOut>(`/v1/ops/companies/${companyId}`, { method: "GET" }, opts);
}

export async function createOpsCompany(
  body: {
    legal_name: string;
    trading_name?: string;
    locale?: string;
    nif?: string;
    admin_email: string;
    admin_role?: string;
  },
  opts: AuthOpts,
): Promise<OpsCompanyDetailOut> {
  return apiJson<OpsCompanyDetailOut>(
    "/v1/ops/companies",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    opts,
  );
}

export async function patchOpsCompany(
  companyId: string,
  body: {
    legal_name?: string;
    trading_name?: string;
    locale?: string;
    max_members?: number;
  },
  opts: AuthOpts,
): Promise<OpsCompanyDetailOut> {
  return apiJson<OpsCompanyDetailOut>(
    `/v1/ops/companies/${companyId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    opts,
  );
}

export async function listMembers(opts: AuthOpts): Promise<MembersBundleOut> {
  return apiJson<MembersBundleOut>("/v1/members", { method: "GET" }, opts);
}

export async function inviteMember(
  email: string,
  role: string,
  opts: AuthOpts,
): Promise<InviteOut> {
  return apiJson<InviteOut>(
    "/v1/members/invites",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role }),
    },
    opts,
  );
}

export async function resendInvite(inviteId: string, opts: AuthOpts): Promise<InviteOut> {
  return apiJson<InviteOut>(
    `/v1/members/invites/${inviteId}/resend`,
    { method: "POST" },
    opts,
  );
}

export async function cancelInvite(inviteId: string, opts: AuthOpts): Promise<InviteOut> {
  return apiJson<InviteOut>(
    `/v1/members/invites/${inviteId}/cancel`,
    { method: "POST" },
    opts,
  );
}

export async function getPublicInvite(token: string): Promise<PublicInviteOut> {
  return apiJson<PublicInviteOut>(`/v1/invites/${token}`, { method: "GET" }, {});
}

export async function acceptInvite(
  token: string,
  body: { password?: string },
  opts: AuthOpts = {},
): Promise<{ status: string; email: string; company_id: string }> {
  return apiJson(
    `/v1/invites/${token}/accept`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    opts,
  );
}
