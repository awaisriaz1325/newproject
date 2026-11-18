"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Alert, Badge, Button, Card, Field, label, statusTone } from "@/components/ui";
import { api, ApiError, readCookie, type Doc, type Org, type Policy } from "@/lib/api";

type Link_ = { id: string; advisor_org_name: string | null; client_org_name: string | null; client_org_id: string; status: string };

const STATES = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC OK OR PA RI SC SD TN TX UT VT VA WV WI".split(" ");

export default function OrgPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const [org, setOrg] = useState<Org | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [links, setLinks] = useState<Link_[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [o, d, p, l] = await Promise.all([
        api<Org>(`/orgs/${orgId}`),
        api<Doc[]>(`/orgs/${orgId}/documents`),
        api<Policy[]>(`/orgs/${orgId}/policies`),
        api<Link_[]>(`/orgs/${orgId}/advisor-links`),
      ]);
      setOrg(o);
      setDocs(d);
      setPolicies(p);
      setLinks(l);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load this workspace.");
    }
  }, [orgId]);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => (active ? load() : undefined));
    return () => {
      active = false;
    };
  }, [load]);
  useEffect(() => {
    if (!docs.some((d) => d.status === "uploaded" || d.status === "processing")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [docs, load]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    setError(null);
    for (const file of Array.from(files)) {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(`/api/orgs/${orgId}/documents`, {
        method: "POST",
        body,
        headers: { "X-CSRF-Token": readCookie("cb_csrf") ?? "" },
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({})))?.detail;
        setError(`${file.name}: ${detail?.message ?? detail ?? "upload failed"}`);
      }
    }
    setUploading(false);
    await load();
  }

  async function createPolicy(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api(`/orgs/${orgId}/policies`, {
        json: {
          carrier_name: f.get("carrier_name"),
          policy_number: f.get("policy_number"),
          state: f.get("state"),
          period_start: f.get("period_start"),
          period_end: f.get("period_end"),
        },
      });
      (e.target as HTMLFormElement).reset();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the policy.");
    }
  }

  async function requestLink(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const code = new FormData(e.currentTarget).get("invite_code");
    try {
      await api(`/orgs/${orgId}/advisor-links`, { json: { invite_code: code } });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed.");
    }
  }

  async function linkAction(id: string, action: "approve" | "revoke") {
    await api(`/orgs/${orgId}/advisor-links/${id}/${action}`, { method: "POST" }).catch((err: unknown) =>
      setError(err instanceof ApiError ? err.message : "Action failed."),
    );
    await load();
  }

  if (!org) return error ? <Alert tone="bad">{error}</Alert> : <p className="text-slate-500">Loading…</p>;
  const isAdvisorFirm = org.kind === "advisor_firm";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">{isAdvisorFirm ? "Advisor firm" : "Employer"} · {org.access === "member" ? org.role : org.access}</p>
          <h1 className="text-2xl font-semibold text-slate-900">{org.name}</h1>
        </div>
        <Link href={`/app/${orgId}/access-log`} className="text-sm font-medium text-emerald-800 underline">
          Who accessed my data
        </Link>
      </div>
      {error && <Alert tone="bad">{error}</Alert>}

      {isAdvisorFirm ? (
        <Card title="Clients">
          <form onSubmit={requestLink} className="mb-4 flex flex-wrap items-end gap-3">
            <Field id="invite_code" name="invite_code" label="Client's invite code" hint="Your client finds it on their CompBack workspace page." required />
            <Button type="submit">Request access</Button>
          </form>
          <ul className="divide-y divide-slate-100">
            {links.map((l) => (
              <li key={l.id} className="flex items-center justify-between py-3 text-sm">
                {l.status === "active" ? (
                  <Link className="font-medium text-emerald-800 underline" href={`/app/${l.client_org_id}`}>
                    {l.client_org_name}
                  </Link>
                ) : (
                  <span>{l.client_org_name}</span>
                )}
                <Badge tone={statusTone(l.status === "active" ? "ready" : l.status)}>{label(l.status)}</Badge>
              </li>
            ))}
            {!links.length && <li className="py-3 text-sm text-slate-500">No clients yet.</li>}
          </ul>
        </Card>
      ) : (
        <>
          <Card
            title="Documents"
            actions={
              <Button onClick={() => fileInput.current?.click()} busy={uploading}>
                Upload documents
              </Button>
            }
          >
            <input ref={fileInput} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.csv,.xlsx" className="sr-only" onChange={(e) => upload(e.target.files)} aria-label="Choose files to upload" />
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                void upload(e.dataTransfer.files);
              }}
              className="mb-4 rounded-md border-2 border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-600"
            >
              Drop your premium audit, policy information page, experience rating worksheet and payroll reports here. PDF, image, CSV or XLSX.
              <span className="mt-1 block text-xs text-slate-500">Social Security numbers are removed automatically before anything is analyzed.</span>
            </div>
            <ul className="divide-y divide-slate-100">
              {docs.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                  <div>
                    <Link href={`/app/${orgId}/documents/${d.id}`} className="font-medium text-slate-900 underline-offset-2 hover:underline">
                      {d.original_filename}
                    </Link>
                    <p className="text-xs text-slate-500">
                      {label(d.doc_type)}
                      {d.page_count ? ` · ${d.page_count} page(s)` : ""}
                      {d.redaction_count ? ` · ${d.redaction_count} identifier(s) redacted` : ""}
                    </p>
                    {d.rejection_message && <p className="text-xs text-red-700">{d.rejection_message}</p>}
                  </div>
                  <Badge tone={statusTone(d.status)}>{label(d.status)}</Badge>
                </li>
              ))}
              {!docs.length && <li className="py-3 text-sm text-slate-500">No documents yet.</li>}
            </ul>
          </Card>

          <Card title="Policies">
            <ul className="mb-5 divide-y divide-slate-100">
              {policies.map((p) => (
                <li key={p.id} className="flex items-center justify-between py-3 text-sm">
                  <Link href={`/app/${orgId}/policies/${p.id}`} className="font-medium text-slate-900 hover:underline">
                    {p.carrier_name} · {p.policy_number}
                  </Link>
                  <span className="text-slate-500">
                    {p.state} · {p.period_start} → {p.period_end}
                  </span>
                </li>
              ))}
              {!policies.length && <li className="py-3 text-sm text-slate-500">Add the policy your audit belongs to.</li>}
            </ul>
            <form onSubmit={createPolicy} className="grid gap-3 sm:grid-cols-3">
              <Field id="carrier_name" name="carrier_name" label="Carrier" required />
              <Field id="policy_number" name="policy_number" label="Policy number" required />
              <div className="flex flex-col gap-1">
                <label htmlFor="state" className="text-sm font-medium text-slate-800">
                  State
                </label>
                <select id="state" name="state" required className="min-h-10 rounded-md border border-slate-300 bg-white px-3 text-sm">
                  {STATES.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              <Field id="period_start" name="period_start" type="date" label="Period start" required />
              <Field id="period_end" name="period_end" type="date" label="Period end" required />
              <div className="flex items-end">
                <Button type="submit" variant="secondary">
                  Add policy
                </Button>
              </div>
            </form>
          </Card>

          {org.invite_code && (
            <Card title="Your advisor">
              <p className="text-sm text-slate-600">
                Want your accountant or broker to help? Give them this invite code: <span className="rounded bg-slate-100 px-2 py-1 font-mono">{org.invite_code}</span>. They only get access after you approve, and you can revoke it any time.
              </p>
              <ul className="mt-3 divide-y divide-slate-100">
                {links.map((l) => (
                  <li key={l.id} className="flex items-center justify-between py-3 text-sm">
                    <span>{l.advisor_org_name}</span>
                    <span className="flex items-center gap-2">
                      <Badge tone={statusTone(l.status === "active" ? "ready" : l.status)}>{label(l.status)}</Badge>
                      {l.status === "pending" && <Button variant="secondary" onClick={() => linkAction(l.id, "approve")}>Approve</Button>}
                      {l.status !== "revoked" && <Button variant="ghost" onClick={() => linkAction(l.id, "revoke")}>Revoke</Button>}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
