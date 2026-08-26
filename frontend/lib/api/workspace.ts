export type Membership = {
  company_id: string;
  role: string;
  is_active: boolean;
};

export type MeOut = {
  id: string;
  email: string;
  user_type: string;
  memberships: Membership[];
};

export type PersonOut = {
  id: string;
  display_name: string | null;
  status: string;
  status_source: string;
  has_source_conflict: boolean;
  leave_type: string | null;
  employment_id: string | null;
  has_contract: boolean;
  review_status: string | null;
  document_id: string | null;
};

export type NotificationItem = {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
  company_id: string | null;
};

export type NotificationList = {
  items: NotificationItem[];
  unread_count: number;
};

export type MismatchFlag = {
  id: string;
  company_id: string;
  company_name: string | null;
  employee_id: string;
  display_name: string | null;
  filename: string | null;
  doc_kind: string | null;
  signed_on: string | null;
  term_end_on: string | null;
  ss_modality: string | null;
  ss_started_on: string | null;
  ss_ended_on: string | null;
  ops_confirmed_at: string | null;
  created_at: string;
};

export type SsBatchOut = {
  id: string;
  period_year_month: string;
  parse_status: string;
  parse_error: string | null;
  uploaded_at: string;
  event_counts: Record<string, number>;
};

export type HeadcountMonthOut = {
  year_month: string;
  headcount: number;
  source: string;
  source_batch_id: string | null;
};

export type BenefitCaseOut = {
  id: string;
  company_id: string;
  company_name: string | null;
  employee_id: string;
  display_name: string | null;
  state: string;
  ineligibility_code: string | null;
  sem_termo_on: string | null;
  window_ends_on: string | null;
  remaining_months: number | null;
  monthly_saving: string | number | null;
};

export type CompanyApplicationOut = {
  id: string;
  company_id: string;
  submitted_on: string | null;
  decision: string;
  headcount_current: number | null;
  headcount_trailing_12_avg: string | number | null;
  headcount_test_pass: boolean | null;
  ss_regularized_at_submit: boolean | null;
  at_regularized_at_submit: boolean | null;
  payroll_not_in_arrears_at_submit: boolean | null;
};

export type CertificateOut = {
  id: string;
  kind: string;
  issued_on: string;
  valid_until: string;
  valid_until_overridden: boolean;
  created_at: string;
};

export type CompanyInvoiceLineOut = {
  description: string;
  fee_amount: string | number;
};

export type CompanyInvoiceOut = {
  id: string;
  company_id: string;
  period_from: string;
  period_to: string;
  status: string;
  currency: string;
  subtotal: string | number;
  tax_amount: string | number;
  total: string | number;
  issued_on: string | null;
  due_on: string | null;
  paid_on: string | null;
  legal_invoice_number: string | null;
  atcud: string | null;
  has_proforma: boolean;
  has_legal_pdf: boolean;
  lines: CompanyInvoiceLineOut[];
};

export type StaffInvoiceLineOut = {
  id: string;
  description: string;
  fee_amount: string | number;
  saving_amount: string | number | null;
  employee_id: string | null;
  benefit_case_id: string | null;
};

export type StaffInvoiceOut = {
  id: string;
  company_id: string;
  period_from: string;
  period_to: string;
  status: string;
  currency: string;
  subtotal: string | number;
  tax_amount: string | number;
  total: string | number;
  issued_on: string | null;
  due_on: string | null;
  paid_on: string | null;
  legal_invoice_number: string | null;
  atcud: string | null;
  certified_external_id: string | null;
  stripe_invoice_id: string | null;
  has_proforma: boolean;
  has_legal_pdf: boolean;
  lines: StaffInvoiceLineOut[];
};

export type BillingSettingsOut = {
  invoicing_method: string | null;
  has_stripe_customer: boolean;
};
