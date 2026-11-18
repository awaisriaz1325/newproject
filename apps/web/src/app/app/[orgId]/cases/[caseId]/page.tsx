"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert, Badge, Button, Card, Field, label, statusTone } from "@/components/ui";
import { api, ApiError, type CaseView } from "@/lib/api";
import { formatRange, formatUsd } from "@/lib/money";

const STEPS = ["draft", "ready_for_review", "approved_by_customer", "submitted", "carrier_responded", "resolved", "fee_invoiced", "closed"];

export default function CasePage() {
  const { orgId, caseId } = useParams<{ orgId: string; caseId: string }>();
  const base = `/orgs/${orgId}/cases/${caseId}`;
  const [c, setC] = useState<CaseView | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => setC(await api<CaseView>(base)), [base]);
  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => (active ? load() : undefined));
    return () => {
      active = false;
    };
  }, [load]);

  async function act(path: string, json?: unknown) {
    setError(null);
    try {
      setC(await api<CaseView>(`${base}${path}`, json === undefined ? { method: "POST" } : { json }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed.");
    }
  }

  function form(path: string, map: (f: FormData) => unknown) {
    return (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      void act(path, map(new FormData(e.currentTarget)));
    };
  }

  if (!c) return <p className="text-slate-500">Loading…</p>;
  const pkg = c.packages.at(-1);
  const idx = STEPS.indexOf(c.status);

  return (
    <div className="space-y-6">
      <Link href={`/app/${orgId}/policies/${c.policy_id}`} className="text-sm text-emerald-800 underline">
        ← Back to analysis
      </Link>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dispute case</h1>
        <Badge tone={statusTone(c.status)}>{label(c.status)}</Badge>
      </div>
      <ol className="flex flex-wrap gap-2 text-xs" aria-label="Case progress">
        {STEPS.map((s, i) => (
          <li key={s} className={`rounded-full px-3 py-1 ${i <= idx ? "bg-emerald-700 text-white" : "bg-slate-200 text-slate-600"}`} aria-current={i === idx ? "step" : undefined}>
            {label(s)}
          </li>
        ))}
      </ol>
      {error && <Alert tone="bad">{error}</Alert>}

      <Card title="Response deadline">
        <p className="text-sm">{c.deadline}</p>
        {c.deadline_source && <p className="text-xs text-slate-500">Source: {c.deadline_source}</p>}
        <form onSubmit={form("/deadline", (f) => ({ deadline_date: f.get("d"), source: f.get("s") }))} className="mt-3 grid gap-3 sm:grid-cols-3">
          <Field id="d" name="d" type="date" label="Deadline" required />
          <Field id="s" name="s" label="Where is this date from?" placeholder="Carrier audit notice dated…" required />
          <div className="flex items-end">
            <Button variant="secondary" type="submit">
              Save deadline
            </Button>
          </div>
        </form>
      </Card>

      <Card title="Dispute package">
        {!pkg ? (
          <Button onClick={() => act("/package")}>Generate package</Button>
        ) : (
          <div className="space-y-3 text-sm">
            <p>
              Version {pkg.version} · estimated total {formatRange(pkg.total_low, pkg.total_high)}
            </p>
            <div className="flex gap-3">
              <a className="font-medium text-emerald-800 underline" href={`/api${base}/package/${pkg.version}.pdf`}>
                Download PDF
              </a>
              <a className="font-medium text-emerald-800 underline" href={`/api${base}/package/${pkg.version}.docx`}>
                Download editable Word file
              </a>
            </div>
            {c.status === "ready_for_review" && (
              <>
                <Alert tone="info">
                  <p className="font-medium">Fees — please read before approving</p>
                  <ul className="mt-1 list-disc pl-5">
                    {c.fee_preview.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </Alert>
                <Button onClick={() => act("/approve")}>I reviewed the package and accept the fee terms</Button>
              </>
            )}
          </div>
        )}
      </Card>

      {c.status === "approved_by_customer" && (
        <Card title="Send it to your carrier">
          <p className="mb-3 text-sm text-slate-600">Send the package yourself (or through your broker). Then record it here so we can track the response.</p>
          <form onSubmit={form("/submitted", (f) => ({ method: f.get("m"), submitted_on: f.get("on") }))} className="grid gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1">
              <label htmlFor="m" className="text-sm font-medium">
                How did you send it?
              </label>
              <select id="m" name="m" className="min-h-10 rounded-md border border-slate-300 px-3 text-sm">
                {["email", "mail", "portal", "fax", "broker"].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </div>
            <Field id="on" name="on" type="date" label="Date sent" required />
            <div className="flex items-end">
              <Button type="submit">Record submission</Button>
            </div>
          </form>
        </Card>
      )}

      {["submitted", "carrier_responded"].includes(c.status) && (
        <Card title="Carrier response">
          <form onSubmit={form("/carrier-response", (f) => ({ note: f.get("note") }))} className="flex flex-wrap items-end gap-3">
            <Field id="note" name="note" label="What did the carrier say?" required />
            <Button type="submit" variant="secondary">
              Log response
            </Button>
          </form>
          {c.status === "carrier_responded" && (
            <form
              onSubmit={form("/outcomes", (f) => ({ kind: f.get("kind"), amount: f.get("amount"), proof_document_id: f.get("proof") || null }))}
              className="mt-4 grid gap-3 sm:grid-cols-4"
            >
              <div className="flex flex-col gap-1">
                <label htmlFor="kind" className="text-sm font-medium">
                  Outcome
                </label>
                <select id="kind" name="kind" className="min-h-10 rounded-md border border-slate-300 px-3 text-sm">
                  {["refund", "credit", "partial", "denied"].map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </div>
              <Field id="amount" name="amount" label="Amount ($)" inputMode="decimal" pattern="\d+(\.\d{1,2})?" required />
              <Field id="proof" name="proof" label="Proof document ID" hint="Upload the carrier's refund/credit notice first." />
              <div className="flex items-end">
                <Button type="submit">Record outcome</Button>
              </div>
            </form>
          )}
        </Card>
      )}

      {(c.outcomes.length > 0 || c.fees.length > 0) && (
        <Card title="Outcome and fees">
          <ul className="space-y-2 text-sm">
            {c.outcomes.map((o) => (
              <li key={o.id}>
                {label(o.kind)} {formatUsd(o.amount)} · {o.verified ? <Badge tone="good">verified</Badge> : <Badge tone="warn">awaiting verification</Badge>}
              </li>
            ))}
            {c.fees.map((f) => (
              <li key={f.id ?? f.kind}>
                {f.kind} fee {formatUsd(f.amount)} · <Badge tone={statusTone(f.status)}>{f.status}</Badge>
                {f.hosted_invoice_url && (
                  <a className="ml-2 underline" href={f.hosted_invoice_url}>
                    View invoice
                  </a>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Timeline">
        <ol className="space-y-1 text-sm text-slate-600">
          {c.events.map((e, i) => (
            <li key={i}>
              <span className="text-xs text-slate-400">{new Date(e.at).toLocaleString()}</span> · {label(e.kind)}
              {e.to ? ` → ${label(e.to)}` : ""}
              {e.note ? ` — ${e.note}` : ""}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
