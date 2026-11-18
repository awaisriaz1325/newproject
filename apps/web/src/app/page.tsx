import Link from "next/link";

const CHECKS = [
  ["Arithmetic", "Every class line, subtotal and total recomputed to the cent."],
  ["Experience mod", "The mod on your bill compared with your experience rating worksheet."],
  ["Promised credits", "Credits on your policy or quote that never made it onto the final bill."],
  ["Payroll", "Audited payroll compared with your own payroll records."],
  ["Overtime", "Overtime premium pay that may have been charged when it should be excluded."],
  ["Duplicates", "The same payroll charged twice under one class."],
];

const STEPS = [
  ["Upload", "Your premium audit, policy information page, experience rating worksheet and payroll summary."],
  ["Free scan", "We recompute your premium independently and show likely errors with an estimated range and the evidence."],
  ["You decide", "If you want, we prepare a dispute package. You or your own broker send it — we never contact your carrier."],
];

export default function Home() {
  return (
    <div className="bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <span className="text-lg font-semibold tracking-tight">
          Comp<span className="text-emerald-700">Back</span>
        </span>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/login" className="text-slate-700 hover:text-slate-900">
            Sign in
          </Link>
          <Link href="/signup" className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800">
            Start free scan
          </Link>
        </nav>
      </header>

      <main>
        <section className="mx-auto max-w-6xl px-6 pb-16 pt-12">
          <p className="text-sm font-medium uppercase tracking-wide text-emerald-700">Workers&apos; comp premium audit review</p>
          <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
            Find out if your workers&apos; comp audit overcharged you.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-slate-600">
            CompBack reads your policy and audit documents, recomputes your premium line by line, and shows any likely overcharges with the page and rule behind each one. You stay in control of what happens next.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/signup" className="rounded-md bg-emerald-700 px-5 py-3 font-medium text-white hover:bg-emerald-800">
              Run a free scan
            </Link>
            <a href="#how" className="rounded-md border border-slate-300 px-5 py-3 font-medium text-slate-800 hover:bg-slate-50">
              How it works
            </a>
          </div>
          <p className="mt-4 text-xs text-slate-500">Estimates are ranges and are not guaranteed. CompBack is software, not legal or insurance advice.</p>
        </section>

        <section id="how" className="border-t border-slate-100 bg-slate-50">
          <div className="mx-auto grid max-w-6xl gap-6 px-6 py-14 sm:grid-cols-3">
            {STEPS.map(([title, body], i) => (
              <div key={title}>
                <p className="text-sm font-semibold text-emerald-700">Step {i + 1}</p>
                <h2 className="mt-1 text-lg font-semibold text-slate-900">{title}</h2>
                <p className="mt-2 text-sm text-slate-600">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-14">
          <h2 className="text-2xl font-semibold text-slate-900">What the scan checks</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CHECKS.map(([title, body]) => (
              <div key={title} className="rounded-lg border border-slate-200 p-5">
                <h3 className="font-semibold text-slate-900">{title}</h3>
                <p className="mt-1 text-sm text-slate-600">{body}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-slate-500">
            Every finding is checked by a reviewer before it goes into a dispute package. Rules that we have not yet verified from official sources are never shown as errors.
          </p>
        </section>

        <section className="border-t border-slate-100 bg-slate-50">
          <div className="mx-auto grid max-w-6xl gap-8 px-6 py-14 sm:grid-cols-2">
            <div>
              <h2 className="text-2xl font-semibold text-slate-900">Built for sensitive documents</h2>
              <ul className="mt-4 space-y-2 text-sm text-slate-700">
                <li>Social Security numbers are detected and removed before analysis — including in scanned pages.</li>
                <li>Documents are encrypted, and every view is recorded in a log you can see.</li>
                <li>Your accountant or broker gets access only after you approve, and you can revoke it any time.</li>
                <li>CompBack staff need a time-limited grant with a stated reason to see your files.</li>
              </ul>
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-slate-900">Pricing</h2>
              <p className="mt-4 text-sm text-slate-700">
                The scan is free. If you choose to prepare a dispute, you&apos;ll see the exact fee terms — a flat analysis fee and a percentage only of refunds or credits you actually receive — before you approve anything.
              </p>
              <p className="mt-3 text-xs text-slate-500">Paid services are being rolled out state by state.</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-8 text-xs text-slate-500">
        <span>© CompBack. Not affiliated with any insurance carrier or rating bureau.</span>
        <span className="flex gap-4">
          <Link href="/legal/terms">Terms</Link>
          <Link href="/legal/privacy">Privacy</Link>
        </span>
      </footer>
    </div>
  );
}
