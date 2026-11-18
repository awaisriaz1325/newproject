"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Alert, Button, Field } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

export default function SignupPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [kind, setKind] = useState<"employer" | "advisor_firm">("employer");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api("/auth/signup", {
        json: {
          email: form.get("email"),
          password: form.get("password"),
          org_name: form.get("org_name"),
          org_kind: kind,
          accept_terms: form.get("terms") === "on",
        },
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Check your email</h1>
        <p className="text-slate-600">
          We sent a verification link. Open it to activate your account, then sign in.
        </p>
        <Link href="/login" className="text-sm font-medium text-emerald-800 underline">
          Go to sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Create your account</h1>
        <p className="mt-1 text-sm text-slate-600">The free scan checks your audit for likely errors. No card needed.</p>
      </div>
      <fieldset className="grid grid-cols-2 gap-2" aria-label="Account type">
        {(["employer", "advisor_firm"] as const).map((k) => (
          <label
            key={k}
            className={`cursor-pointer rounded-md border px-3 py-2 text-sm ${kind === k ? "border-emerald-700 bg-emerald-50" : "border-slate-300"}`}
          >
            <input type="radio" name="kind" className="sr-only" checked={kind === k} onChange={() => setKind(k)} />
            <span className="font-medium">{k === "employer" ? "I'm an employer" : "I'm an advisor"}</span>
            <span className="block text-xs text-slate-500">{k === "employer" ? "Check my own policy" : "Accountant, broker or consultant"}</span>
          </label>
        ))}
      </fieldset>
      <Field id="org_name" name="org_name" label={kind === "employer" ? "Business name" : "Firm name"} required autoComplete="organization" />
      <Field id="email" name="email" type="email" label="Work email" required autoComplete="email" />
      <Field id="password" name="password" type="password" label="Password" required minLength={12} autoComplete="new-password" hint="At least 12 characters." />
      <label className="flex items-start gap-2 text-sm text-slate-700">
        <input type="checkbox" name="terms" className="mt-1" required />
        <span>
          I agree to the <Link href="/legal/terms" className="underline">Terms</Link> and{" "}
          <Link href="/legal/privacy" className="underline">Privacy Policy</Link>, and consent to CompBack processing my documents to provide the service.
        </span>
      </label>
      {error && <Alert tone="bad">{error}</Alert>}
      <Button type="submit" busy={busy} className="w-full">
        Create account
      </Button>
      <p className="text-center text-sm text-slate-600">
        Already have an account? <Link href="/login" className="font-medium text-emerald-800 underline">Sign in</Link>
      </p>
    </form>
  );
}
