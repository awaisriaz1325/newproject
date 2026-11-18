export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6 py-16">
      <p className="text-sm font-medium uppercase tracking-wide text-emerald-700">CompBack</p>
      <h1 className="text-4xl font-semibold tracking-tight text-slate-900">
        Check your workers&apos; comp premium audit for errors.
      </h1>
      <p className="text-lg text-slate-600">
        Upload your policy and audit documents. CompBack recomputes your premium independently
        and shows any likely overcharges with the evidence behind them. You stay in control:
        you or your own advisor decide whether to dispute.
      </p>
      <p className="text-sm text-slate-500">
        Estimates are not guaranteed. CompBack is software, not legal or insurance advice.
      </p>
    </main>
  );
}
