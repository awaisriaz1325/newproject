"use client";

import Link from "next/link";
import { Badge, Card } from "@/components/ui";
import { useSession } from "@/components/session";

export default function Dashboard() {
  const { me } = useSession();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Your workspaces</h1>
        {!me.email_verified && <p className="mt-2 text-sm text-amber-800">Verify your email to upload documents.</p>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {me.memberships.map((m) => (
          <Link key={m.org_id} href={`/app/${m.org_id}`} className="block rounded-lg focus-visible:outline-2 focus-visible:outline-emerald-700">
            <Card className="h-full transition hover:border-emerald-600">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-slate-900">{m.org_name}</p>
                  <p className="text-sm text-slate-500">{m.org_kind === "advisor_firm" ? "Advisor firm" : "Employer"}</p>
                </div>
                <Badge>{m.role}</Badge>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
