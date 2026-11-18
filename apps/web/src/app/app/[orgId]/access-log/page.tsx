"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Card, label } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

type Entry = { seq: number; action: string; actor_kind: string; reason: string | null; created_at: string; details: Record<string, unknown> };

export default function AccessLogPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const [rows, setRows] = useState<Entry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Entry[]>(`/orgs/${orgId}/access-log`)
      .then(setRows)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not load the log."));
  }, [orgId]);

  return (
    <div className="space-y-5">
      <Link href={`/app/${orgId}`} className="text-sm text-emerald-800 underline">
        ← Back
      </Link>
      <h1 className="text-2xl font-semibold">Who accessed your data</h1>
      <p className="text-sm text-slate-600">Every view or download of your documents, every advisor link, and every time CompBack staff were granted temporary access (with their stated reason).</p>
      {error && <Alert tone="bad">{error}</Alert>}
      <Card>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr>
              <th scope="col" className="py-2">When</th>
              <th scope="col">What</th>
              <th scope="col">Who</th>
              <th scope="col">Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((r) => (
              <tr key={r.seq} className="border-t border-slate-100">
                <td className="py-2 pr-3 text-slate-500">{new Date(r.created_at).toLocaleString()}</td>
                <td className="pr-3">{label(r.action.replace(".", " "))}</td>
                <td className="pr-3">{r.actor_kind === "reviewer" ? "CompBack reviewer" : label(r.actor_kind)}</td>
                <td>{r.reason ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows && !rows.length && <p className="py-3 text-sm text-slate-500">No access recorded yet.</p>}
      </Card>
    </div>
  );
}
