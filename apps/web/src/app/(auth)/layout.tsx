import Link from "next/link";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="px-6 py-5">
        <Link href="/" className="text-lg font-semibold tracking-tight text-slate-900">
          Comp<span className="text-emerald-700">Back</span>
        </Link>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pb-16 pt-6">
        <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm">{children}</div>
      </main>
    </div>
  );
}
