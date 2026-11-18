"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Alert, Button, Field } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<"password" | "mfa">("password");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onPassword(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ mfa_required: boolean }>("/auth/login", {
        json: { email: form.get("email"), password: form.get("password") },
      });
      if (res.mfa_required) setStep("mfa");
      else router.push("/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onCode(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const code = String(new FormData(e.currentTarget).get("code") ?? "").trim();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/mfa/verify", { json: code.includes("-") ? { recovery_code: code } : { code } });
      router.push("/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That code didn't work.");
    } finally {
      setBusy(false);
    }
  }

  if (step === "mfa") {
    return (
      <form onSubmit={onCode} className="space-y-5">
        <h1 className="text-2xl font-semibold text-slate-900">Two-factor authentication</h1>
        <Field id="code" name="code" label="6-digit code or recovery code" inputMode="numeric" autoComplete="one-time-code" required />
        {error && <Alert tone="bad">{error}</Alert>}
        <Button type="submit" busy={busy} className="w-full">
          Verify
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={onPassword} className="space-y-5">
      <h1 className="text-2xl font-semibold text-slate-900">Sign in</h1>
      <Field id="email" name="email" type="email" label="Email" required autoComplete="email" />
      <Field id="password" name="password" type="password" label="Password" required autoComplete="current-password" />
      {error && <Alert tone="bad">{error}</Alert>}
      <Button type="submit" busy={busy} className="w-full">
        Sign in
      </Button>
      <p className="text-center text-sm text-slate-600">
        New here? <Link href="/signup" className="font-medium text-emerald-800 underline">Create an account</Link>
      </p>
    </form>
  );
}
