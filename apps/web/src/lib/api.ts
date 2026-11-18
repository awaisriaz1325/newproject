/**
 * Browser API client. All calls go to same-origin /api/* (proxied to FastAPI by next.config.ts),
 * so the HttpOnly session cookie is first-party. Mutations send the CSRF token from the cb_csrf
 * cookie (double-submit). The API returns money as decimal strings; never parse them as floats.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function readCookie(name: string, cookieString: string = globalThis.document?.cookie ?? ""): string | null {
  for (const part of cookieString.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

function errorFrom(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail, humanize(detail));
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { code?: string; message: string };
    return new ApiError(status, d.code ?? "error", d.message);
  }
  if (Array.isArray(detail)) return new ApiError(status, "invalid", "Please check the highlighted fields.");
  return new ApiError(status, "error", "Something went wrong. Please try again.");
}

const MESSAGES: Record<string, string> = {
  email_not_verified: "Please verify your email first. Check your inbox for the link.",
  mfa_required: "Enter the 6-digit code from your authenticator app.",
  mfa_enrollment_required: "Your role requires two-factor authentication. Set it up to continue.",
  "invalid email or password": "That email and password don't match.",
  "authentication required": "Please sign in.",
};

export function humanize(code: string): string {
  return MESSAGES[code] ?? code.charAt(0).toUpperCase() + code.slice(1);
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const method = (init.method ?? (init.json !== undefined ? "POST" : "GET")).toUpperCase();
  const headers = new Headers(init.headers);
  if (init.json !== undefined) headers.set("Content-Type", "application/json");
  if (method !== "GET") headers.set("X-CSRF-Token", readCookie("cb_csrf") ?? "anonymous");
  const res = await fetch(`/api${path}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
    body: init.json !== undefined ? JSON.stringify(init.json) : init.body,
  });
  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) throw errorFrom(res.status, body);
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export type Membership = { org_id: string; org_name: string; org_kind: string; role: string };
export type Me = {
  id: string;
  email: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  mfa_verified: boolean;
  mfa_required: boolean;
  is_platform_staff: boolean;
  memberships: Membership[];
};
export type Org = { id: string; name: string; kind: string; access: string; role: string; invite_code: string | null };
export type Doc = {
  id: string;
  original_filename: string;
  doc_type: string;
  status: string;
  page_count: number | null;
  redaction_count: number | null;
  rejection_message: string | null;
  quality_flags: string[];
  created_at: string;
};
export type Page = { page_no: number; text_source: string; ocr_confidence: string | null; has_image: boolean };
export type DocDetail = Doc & { pages: Page[] };
export type Fld = { value: string | null; page: number | null; confidence: number };
export type ClassLine = {
  state: string | null;
  class_code: string;
  description: string | null;
  payroll: string | null;
  rate: string | null;
  premium: string | null;
  page: number | null;
  confidence: number;
};
export type Issue = { code: string; message: string; field: string; expected: string | null; found: string | null };
export type Extraction = {
  id: string;
  doc_type: string;
  status: string;
  extractor: string;
  review_reasons: string[];
  issues: Issue[];
  data: Record<string, unknown>;
};
export type Policy = {
  id: string;
  carrier_name: string;
  policy_number: string;
  state: string;
  period_start: string;
  period_end: string;
  document_ids: string[];
};
export type Finding = {
  id: string;
  detector: string;
  rule_id: string;
  rule_status: string;
  citations: { source: string; section: string; url: string | null }[];
  title: string;
  explanation: string;
  conditions: string[];
  evidence: { document_id: string | null; page: number | null; field: string }[];
  impact_low: string;
  impact_high: string;
  confidence: string;
  customer_visible: boolean;
  reviewer_status: string;
};
export type Analysis = {
  recomputation_id: string;
  billed_total: string;
  recomputed_total: string;
  estimate_low: string;
  estimate_high: string;
  estimate_label: string;
  steps: { label: string; formula: string; result: string; rule_id: string | null }[];
  findings: Finding[];
};
export type CaseView = {
  id: string;
  policy_id: string;
  status: string;
  submitter_mode: string;
  deadline: string;
  deadline_source: string | null;
  events: { kind: string; from: string | null; to: string | null; note: string | null; at: string }[];
  packages: { id: string; version: number; total_low: string; total_high: string; approved_at: string | null }[];
  outcomes: { id: string; kind: string; amount: string; verified: boolean }[];
  fees: { id: string | null; kind: string; amount: string; status: string; lines: string[]; hosted_invoice_url: string | null }[];
  fee_preview: string[];
};
