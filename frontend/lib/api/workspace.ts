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

export type CompanyScopeOut = {
  company_id: string;
  legal_name: string;
  role: string | null;
  actor: string;
  ss_no_debt_valid_until: string | null;
  at_no_debt_valid_until: string | null;
  estimate_now_monthly: string | number | null;
  estimate_now_window: string | number | null;
  estimate_potential_monthly: string | number | null;
  estimate_potential_window: string | number | null;
  estimate_unconfirmed: boolean;
  contracts_missing: number;
};

export type EstablishmentOut = {
  id: string;
  name: string;
  ss_code: string;
  status: "OPEN" | "CLOSED" | string;
  created_at: string;
};

export type TermBenefitReading = {
  rule: "certo_renewal" | "years_2" | "years_3" | "years_4" | "incerto_4";
  deemed_on: string;
  can_benefit: boolean;
};

export type TermBenefitOut = {
  flagged: boolean;
  readings: TermBenefitReading[];
  early_earliest?: string | null;
  early_latest?: string | null;
  early_suggested?: string | null;
};

export type BenefitBlockOut = {
  reason:
    | "no_start"
    | "employment_ended"
    | "age_at_start"
    | "window_over"
    | "term_no_day"
    | "term_early_over"
    | "term_dates_over"
    | "other_modality";
  contract_started_on?: string | null;
  age_on_start?: number | null;
  counted_to?: string | null;
  last_day?: string | null;
};

export type PersonOut = {
  id: string;
  display_name: string | null;
  status: string;
  status_source: string;
  has_source_conflict: boolean;
  leave_type: string | null;
  employment_id: string | null;
  contract_modality: string | null;
  has_contract: boolean;
  review_status: string | null;
  document_id: string | null;
  already_on_ss_reduction: boolean;
  age?: number | null;
  contract_started_on?: string | null;
  benefit_outlook?: "already" | "might" | "never" | null;
  benefit_block?: BenefitBlockOut | null;
  term_benefit?: TermBenefitOut | null;
  request_case_stage?: string | null;
  residence?: string | null;
};

export type PipelineStageOut = {
  id: string;
  code: string;
  name: string;
  stage_type: string;
  position: number;
  entry_path: string | null;
  operations: string[];
};

export type RequestMove = {
  operation: string;
  stage_id: string;
  outcome: "favorable" | "unfavorable" | "claim" | null;
};

export type RequestCaseOut = {
  id: string;
  company_id: string;
  company_name: string;
  employee_id: string;
  display_name: string | null;
  stage_id: string;
  stage_code: string;
  stage_name: string;
  stage_type: string;
  opened_at: string;
  stage_entered_at: string;
  path: string;
  applied_on: string | null;
  benefit_starts_on: string | null;
  probation_ends_on: string | null;
  minuta_sent: boolean;
  minuta_id: string | null;
  notice_file_id: string | null;
  operations?: string[];
  moves?: RequestMove[];
  can_claim?: boolean;
  can_attach_scan?: boolean;
  remaining_months?: number | null;
  person_name?: string | null;
  person_address?: string | null;
  person_nif?: string | null;
  person_niss?: string | null;
  company_address?: string | null;
  company_signatory_name?: string | null;
  company_nif?: string | null;
  company_niss?: string | null;
  contract_started_on?: string | null;
  converted_on?: string | null;
  declared_on?: string | null;
  signed_place?: string | null;
  draft_html?: string | null;
  events?: RequestCaseEvent[];
};

export type RequestCaseEvent = {
  id: string;
  at: string;
  actor_id?: string | null;
  from_stage_id?: string | null;
  to_stage_id: string;
  from_stage_name?: string | null;
  to_stage_name: string;
  from_stage_code?: string | null;
  to_stage_code: string;
  operation?: string | null;
  payload?: Record<string, unknown>;
};

export type MinutaTemplateOut = {
  id: string;
  code: string;
  title: string;
  body_html: string;
  is_active: boolean;
};

export type MinutaTokenOut = {
  key: string;
  group: string;
};

export type RejectionReasonOut = {
  id: string;
  code: string;
  label: string;
  blocks_claim: boolean;
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

export type MemberOut = {
  id: string;
  user_id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type InviteOut = {
  id: string;
  email: string;
  role: string;
  status: string;
  needs_password: boolean;
  expires_at: string;
  sent_at: string | null;
  last_error: string | null;
  created_at: string;
  invite_url?: string | null;
};

export type MembersBundleOut = {
  max_members: number;
  seats_used: number;
  members: MemberOut[];
  invites: InviteOut[];
};

export type OpsCompanyListOut = {
  id: string;
  legal_name: string;
  trading_name: string | null;
  locale: string;
  status: string;
  max_members: number;
  seats_used: number;
  has_nif: boolean;
  created_from_intake_id: string | null;
  created_at: string;
};

export type OpsCompanyDetailOut = OpsCompanyListOut & {
  members: MemberOut[];
  invites: InviteOut[];
  invite_url?: string | null;
  registered_address?: string | null;
  signatory_name?: string | null;
  ss_subconta_username?: string | null;
  has_ss_subconta_password?: boolean;
  ss_subconta_available_on?: string | null;
};

export type SsSubcontaRevealOut = {
  username: string | null;
  password: string | null;
};

export type PublicInviteOut = {
  company_name: string;
  email: string;
  given_name?: string | null;
  family_name?: string | null;
  role: string;
  status: string;
  needs_password: boolean;
  expires_at: string;
};
