"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, label, statusTone } from "@/components/ui";
import { api, ApiError, type ClassLine, type DocDetail, type Extraction, type Fld } from "@/lib/api";

const SCALAR_LABELS: Record<string, string> = {
  carrier_name: "Carrier",
  policy_number: "Policy number",
  period_start: "Period start",
  period_end: "Period end",
  total_manual_premium: "Total manual premium",
  experience_mod: "Experience mod",
  schedule_mod: "Schedule credit/debit",
  premium_discount: "Premium discount",
  expense_constant: "Expense constant",
  total_premium: "Total premium",
  previously_billed: "Previously billed",
  balance: "Balance",
  total_gross_wages: "Total gross wages",
  overtime_premium_pay: "Overtime premium pay",
  rating_effective_date: "Rating effective date",
};

function isFld(v: unknown): v is Fld {
  return !!v && typeof v === "object" && "confidence" in v && "value" in v;
}

export default function DocumentPage() {
  const { orgId, docId } = useParams<{ orgId: string; docId: string }>();
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [ext, setExt] = useState<Extraction | null>(null);
  const [page, setPage] = useState(1);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<{ tone: "good" | "bad"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setDoc(await api<DocDetail>(`/orgs/${orgId}/documents/${docId}`));
    setExt(await api<Extraction>(`/orgs/${orgId}/documents/${docId}/extraction`).catch(() => null));
  }, [orgId, docId]);
  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => (active ? load() : undefined));
    return () => {
      active = false;
    };
  }, [load]);

  async function save() {
    const list = Object.entries(edits).map(([path, value]) => ({ path, value: value === "" ? null : value }));
    if (!list.length) return;
    setBusy(true);
    try {
      setExt(await api<Extraction>(`/orgs/${orgId}/documents/${docId}/extraction`, { method: "PATCH", json: { edits: list } }));
      setEdits({});
      setMessage({ tone: "good", text: "Corrections saved." });
    } catch (err) {
      setMessage({ tone: "bad", text: err instanceof ApiError ? err.message : "Could not save." });
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setBusy(true);
    try {
      setExt(await api<Extraction>(`/orgs/${orgId}/documents/${docId}/extraction/verify`, { method: "POST" }));
      setMessage({ tone: "good", text: "Marked as verified. It can now be used in the analysis." });
    } finally {
      setBusy(false);
    }
  }

  if (!doc) return <p className="text-slate-500">Loading…</p>;
  const pages = doc.pages.filter((p) => p.has_image);
  const data = ext?.data ?? {};
  const lines = (data.class_lines as ClassLine[] | undefined) ?? [];

  const input = (path: string, value: string | null, conf?: number) => (
    <input
      aria-label={path}
      defaultValue={value ?? ""}
      onChange={(e) => setEdits((prev) => ({ ...prev, [path]: e.target.value }))}
      className={`w-full rounded border px-2 py-1 text-sm ${conf !== undefined && conf < 0.9 ? "border-amber-400 bg-amber-50" : "border-slate-300"}`}
    />
  );

  return (
    <div className="space-y-5">
      <Link href={`/app/${orgId}`} className="text-sm text-emerald-800 underline">
        ← Back
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-900">{doc.original_filename}</h1>
        <div className="flex gap-2">
          <Badge>{label(doc.doc_type)}</Badge>
          <Badge tone={statusTone(doc.status)}>{label(doc.status)}</Badge>
        </div>
      </div>
      {doc.rejection_message && <Alert tone="bad">{doc.rejection_message}</Alert>}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={`Page ${page} of ${pages.length || doc.page_count || 1} (redacted copy)`}>
          {pages.length ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element -- authenticated, watermarked API image */}
              <img src={`/api/orgs/${orgId}/documents/${docId}/pages/${page}/image`} alt={`Redacted page ${page}`} className="w-full rounded border" />
              <div className="mt-3 flex gap-2">
                <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Previous
                </Button>
                <Button variant="secondary" disabled={page >= pages.length} onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">No page images for this file type.</p>
          )}
        </Card>
        <Card
          title="Extracted values"
          actions={ext && <Badge tone={statusTone(ext.status)}>{label(ext.status)}</Badge>}
        >
          {!ext && <p className="text-sm text-slate-500">Extraction runs automatically after processing.</p>}
          {ext && (
            <div className="space-y-4">
              {ext.review_reasons.length > 0 && (
                <Alert tone="warn">Please check: {ext.review_reasons.map(label).join(", ")}. Fields highlighted in amber have low confidence.</Alert>
              )}
              {ext.issues.map((i) => (
                <Alert key={i.field + i.code} tone="warn">
                  {i.message}
                  {i.expected && ` (expected ${i.expected}, document shows ${i.found})`}
                </Alert>
              ))}
              <dl className="grid grid-cols-[1fr_1.4fr] items-center gap-x-3 gap-y-2 text-sm">
                {Object.entries(data)
                  .filter(([, v]) => isFld(v))
                  .map(([k, v]) => {
                    const f = v as Fld;
                    return (
                      <div key={k} className="contents">
                        <dt className="text-slate-600">
                          {SCALAR_LABELS[k] ?? label(k)}
                          {f.page ? <span className="text-xs text-slate-400"> · p{f.page}</span> : null}
                        </dt>
                        <dd>{input(k, f.value, f.value === null ? undefined : f.confidence)}</dd>
                      </div>
                    );
                  })}
              </dl>
              {lines.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <caption className="mb-2 text-left font-medium text-slate-800">Class lines</caption>
                    <thead className="text-left text-xs text-slate-500">
                      <tr>
                        <th scope="col">Code</th>
                        <th scope="col">Payroll</th>
                        <th scope="col">Rate</th>
                        <th scope="col">Premium</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lines.map((l, i) => (
                        <tr key={i}>
                          <td className="py-1 pr-2 font-mono">{l.class_code}</td>
                          <td className="pr-2">{input(`class_lines[${i}].payroll`, l.payroll, l.confidence)}</td>
                          <td className="pr-2">{input(`class_lines[${i}].rate`, l.rate, l.confidence)}</td>
                          <td>{input(`class_lines[${i}].premium`, l.premium, l.confidence)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {message && <Alert tone={message.tone}>{message.text}</Alert>}
              <div className="flex gap-2">
                <Button variant="secondary" onClick={save} busy={busy} disabled={!Object.keys(edits).length}>
                  Save corrections
                </Button>
                <Button onClick={verify} busy={busy} disabled={ext.status === "verified"}>
                  Values match the document
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
