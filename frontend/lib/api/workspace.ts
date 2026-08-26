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
