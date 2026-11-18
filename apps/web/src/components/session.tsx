"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Alert, Button, Field } from "@/components/ui";
import { api, ApiError, type Me } from "@/lib/api";

const SessionContext = createContext<{ me: Me; reload: () => void } | null>(null);

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside SessionProvider");
  return ctx;
}

function MfaGate({ me, onDone }: { me: Me; onDone: () => void }) {
  const [uri, setUri] = useState<string | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    try {
      setUri((await api<{ otpauth_uri: string }>("/auth/mfa/setup", { method: "POST" })).otpauth_uri);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start setup.");
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const code = String(new FormData(e.currentTarget).get("code") ?? "");
    setBusy(true);
    setError(null);
    try {
      if (me.mfa_enabled) {
        await api("/auth/mfa/verify", { json: { code } });
        onDone();
      } else {
        setCodes((await api<{ recovery_codes: string[] }>("/auth/mfa/enable", { json: { code } })).recovery_codes);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That code didn't work.");
    } finally {
      setBusy(false);
    }
  }

  if (codes) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Save your recovery codes</h1>
        <p className="text-sm text-slate-600">Each code works once if you lose your phone. They won&apos;t be shown again.</p>
        <ul className="grid grid-cols-2 gap-2 rounded-md bg-slate-50 p-4 font-mono text-sm">
          {codes.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        <Button onClick={onDone}>I saved them</Button>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <h1 className="text-xl font-semibold">Two-factor authentication required</h1>
      {!me.mfa_enabled && !uri && (
        <>
          <p className="text-sm text-slate-600">Advisors and reviewers must use an authenticator app (Google Authenticator, 1Password, Authy…).</p>
          <Button type="button" onClick={start} busy={busy}>
            Set up authenticator
          </Button>
        </>
      )}
      {uri && (
        <div className="space-y-2 text-sm">
          <p>Add this key to your authenticator app (or open the link on your phone):</p>
          <a href={uri} className="block break-all rounded bg-slate-50 p-3 font-mono text-xs">
            {new URL(uri).searchParams.get("secret")}
          </a>
        </div>
      )}
      {(me.mfa_enabled || uri) && (
        <>
          <Field id="code" name="code" label="6-digit code" inputMode="numeric" autoComplete="one-time-code" required />
          <Button type="submit" busy={busy}>
            Verify
          </Button>
        </>
      )}
      {error && <Alert tone="bad">{error}</Alert>}
    </form>
  );
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const load = useCallback(() => {
    api<Me>("/auth/me")
      .then(setMe)
      .catch(() => router.replace("/login"));
  }, [router]);
  useEffect(load, [load]);

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }

  if (!me) return <p className="p-8 text-slate-500">Loading…</p>;
  const needsMfa = me.mfa_required && !me.mfa_verified;
  return (
    <SessionContext.Provider value={{ me, reload: load }}>
      <div className="min-h-screen bg-slate-50">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
            <Link href="/app" className="text-lg font-semibold tracking-tight">
              Comp<span className="text-emerald-700">Back</span>
            </Link>
            <div className="flex items-center gap-3 text-sm text-slate-600">
              <span className="hidden sm:inline">{me.email}</span>
              <Button variant="ghost" onClick={signOut}>
                Sign out
              </Button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">
          {needsMfa ? (
            <div className="mx-auto max-w-md rounded-xl border bg-white p-8">
              <MfaGate me={me} onDone={load} />
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </SessionContext.Provider>
  );
}
