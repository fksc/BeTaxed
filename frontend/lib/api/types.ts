export const HEADER_INTAKE_SESSION = "X-Intake-Session";
export const HEADER_COMPANY_ID = "X-Company-Id";

export type IntakeBatchSummary = {
  id: string;
  parse_status: string;
  parse_error: string | null;
  vinculo_count: number;
  contrato_count: number;
  period_year_month: string;
};

export type IntakeOut = {
  id: string;
  status: string;
  user_id: string | null;
  teaser_now_monthly: string | number | null;
  teaser_now_window: string | number | null;
  teaser_potential_monthly: string | number | null;
  teaser_potential_window: string | number | null;
  teaser_currency: string;
  converted_company_id: string | null;
  latest_batch: IntakeBatchSummary | null;
  verbose_people?: VerbosePerson[] | null;
  session_token?: string | null;
  company_id?: string;
  membership_role?: string | null;
};

export type VerbosePerson = {
  name: string | null;
  age: number | null;
  contract: string;
  contract_label: string | null;
  started_on: string | null;
  salary: string | number | null;
  bucket: "now" | "potential" | "none";
  how_code: string;
  remaining_months: number | null;
  monthly_eur: string | number | null;
  window_eur: string | number | null;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
