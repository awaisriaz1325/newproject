"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, label, statusTone } from "@/components/ui";
import { api, ApiError, type Analysis, type Doc, type Policy } from "@/lib/api";
import { formatRange, formatUsd } from "@/lib/money";

export default function PolicyPage() {
  const { orgId, policyId } = useParams<{ orgId: string; policyId: string }>();
  const router = useRouter();
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSteps, setShowSteps] = useState(false);

  const load = useCallback(async () => {
    const pols = await api<Policy[]>(`/orgs/${orgId}/policies`);
    setPolicy(pols.find((p) => p.id === policyId) ?? null);
    setDocs(await api<Doc[]>(`/orgs/${orgId}/documents`));
    setAnalysis(await api<Analysis>(`/orgs/${orgId}/policies/${policyId}/analysis`).catch(() => null));
  }, [orgId, policyId]);
  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => (active ? load() : undefined));
    return () => {
      active = false;
    };
  }, [load]);

  async function attach(docId: string) {
    await api(`/orgs/${orgId}/policies/${policyId}/documents/${docId}`, { method: "POST" });
    await load();
  }

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setAnalysis(await api<Analysis>(`/orgs/${orgId}/policies/${policyId}/analyze`, { method: "POST" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  async function openCase() {
    try {
      const c = await api<{ id: string }>(`/orgs/${orgId}/cases`, { json: { policy_id: policyId } });
      router.push(`/app/${orgId}/cases/${c.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not open a case.");
    }
  }

  if (!policy) return <p className="text-slate-500">Loading…</p>;
  const attached = new Set(policy.document_ids);

  return (
    <div className="space-y-6">
      <Link href={`/app/${orgId}`} className="text-sm text-emerald-800 underline">
        ← Back
      </Link>
      <div>
        <p className="text-sm text-slate-500">
          {policy.state} · {policy.period_start} → {policy.period_end}
        </p>
        <h1 className="text-2xl font-semibold text-slate-900">
          {policy.carrier_name} · {policy.policy_number}
        </h1>
      </div>

      <Card title="Documents for this policy">
        <ul className="divide-y divide-slate-100 text-sm">
          {docs
            .filter((d) => d.status === "ready")
            .map((d) => (
              <li key={d.id} className="flex items-center justify-between py-2">
                <span>
                  {d.original_filename} <span className="text-slate-500">· {label(d.doc_type)}</span>
                </span>
                {attached.has(d.id) ? (
                  <Badge tone="good">attached</Badge>
                ) : (
                  <Button variant="secondary" onClick={() => attach(d.id)}>
                    Attach
                  </Button>
                )}
              </li>
            ))}
        </ul>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={run} busy={busy}>
            {analysis ? "Re-run free scan" : "Run free scan"}
          </Button>
          <span className="text-xs text-slate-500">Uses only values you have verified or that passed all checks.</span>
        </div>
        {error && (
          <div className="mt-3">
            <Alert tone="bad">{error}</Alert>
          </div>
        )}
      </Card>

      {analysis && (
        <>
          <Card title="Free scan result">
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Billed premium</p>
                <p className="text-xl font-semibold">{formatUsd(analysis.billed_total)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Recomputed</p>
                <p className="text-xl font-semibold">{formatUsd(analysis.recomputed_total)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Estimated possible overcharge</p>
                <p className="text-xl font-semibold text-emerald-800">{formatRange(analysis.estimate_low, analysis.estimate_high)}</p>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">{analysis.estimate_label}</p>
            {analysis.findings.length === 0 && (
              <div className="mt-4">
                <Alert tone="good">We did not find likely errors in the documents provided. That is a good outcome.</Alert>
              </div>
            )}
          </Card>

          {analysis.findings.map((f) => (
            <Card key={f.id} title={f.title} actions={<Badge tone={statusTone(f.reviewer_status)}>{label(f.reviewer_status)}</Badge>}>
              <p className="text-sm text-slate-700">{f.explanation}</p>
              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-slate-500">Estimated effect</dt>
                  <dd className="font-medium">{formatRange(f.impact_low, f.impact_high)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Confidence</dt>
                  <dd>{Math.round(Number(f.confidence) * 100)}%</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Basis</dt>
                  <dd>
                    {f.citations.length
                      ? f.citations.map((c) =>
                          c.url ? (
                            <a key={c.section} href={c.url} className="underline" target="_blank" rel="noreferrer">
                              {c.source} {c.section}
                            </a>
                          ) : (
                            <span key={c.section}>{c.source}</span>
                          ),
                        )
                      : f.rule_id}
                  </dd>
                </div>
              </dl>
              {f.conditions.length > 0 && <p className="mt-2 text-xs text-slate-500">To confirm: {f.conditions.join("; ")}.</p>}
              <p className="mt-2 text-xs text-slate-500">
                Evidence: {f.evidence.map((e) => `${e.field}${e.page ? ` (page ${e.page})` : ""}`).join(", ")}
              </p>
            </Card>
          ))}

          <Card
            title="How we recomputed your premium"
            actions={
              <Button variant="ghost" onClick={() => setShowSteps(!showSteps)} aria-expanded={showSteps}>
                {showSteps ? "Hide" : "Show"} steps
              </Button>
            }
          >
            {showSteps && (
              <table className="w-full text-sm">
                <tbody>
                  {analysis.steps.map((s, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="py-1.5 pr-3">{s.label}</td>
                      <td className="pr-3 font-mono text-xs text-slate-500">{s.formula}</td>
                      <td className="text-right font-medium">{formatUsd(s.result)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          {analysis.findings.some((f) => f.reviewer_status === "confirmed") && (
            <Card title="Next step">
              <p className="mb-3 text-sm text-slate-600">
                Prepare a dispute package with the confirmed items. You review it, then you (or your own broker or advisor) send it to your carrier. CompBack never contacts your carrier.
              </p>
              <Button onClick={openCase}>Prepare dispute package</Button>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
