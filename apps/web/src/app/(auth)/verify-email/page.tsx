"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Alert } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

function Verify() {
  const token = useSearchParams().get("token");
  const [state, setState] = useState<"working" | "ok" | "error">(token ? "working" : "error");
  const [message, setMessage] = useState(token ? "" : "This link is missing its token.");

  useEffect(() => {
    if (!token) return;
    api("/auth/verify-email", { json: { token } })
      .then(() => setState("ok"))
      .catch((err: unknown) => {
        setState("error");
        setMessage(err instanceof ApiError ? err.message : "Verification failed.");
      });
  }, [token]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900">Email verification</h1>
      {state === "working" && <p className="text-slate-600">Verifying…</p>}
      {state === "ok" && <Alert tone="good">Your email is verified. You can sign in now.</Alert>}
      {state === "error" && <Alert tone="bad">{message} The link may have expired; sign up again to get a new one.</Alert>}
      <Link href="/login" className="text-sm font-medium text-emerald-800 underline">
        Go to sign in
      </Link>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<p className="text-slate-600">Loading…</p>}>
      <Verify />
    </Suspense>
  );
}
