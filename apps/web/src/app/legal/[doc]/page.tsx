import Link from "next/link";

const DOCS: Record<string, { title: string; body: string[] }> = {
  terms: {
    title: "Terms of Service",
    body: [
      "PLACEHOLDER — These terms have not been reviewed by counsel and are not in effect. They will be replaced before launch (founder decision FD-11).",
      "CompBack is software that analyzes documents you provide and prepares materials for you to review. It is not legal advice, insurance advice, or a public adjusting service. You decide whether and how to contact your carrier.",
      "Estimated amounts are ranges and are not guaranteed.",
    ],
  },
  privacy: {
    title: "Privacy Policy",
    body: [
      "PLACEHOLDER — This policy has not been reviewed by counsel and will be replaced before launch (founder decision FD-11).",
      "We remove Social Security numbers from uploaded documents before analysis and do not store them. Documents are encrypted at rest; each access is logged and visible to you.",
      "We use third-party processors (hosting, storage, and an AI model provider configured not to train on your data). You can delete your documents at any time.",
    ],
  },
};

export function generateStaticParams() {
  return Object.keys(DOCS).map((doc) => ({ doc }));
}

export default async function LegalPage({ params }: { params: Promise<{ doc: string }> }) {
  const { doc } = await params;
  const content = DOCS[doc] ?? DOCS.terms;
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <Link href="/" className="text-sm text-emerald-800 underline">
        ← CompBack
      </Link>
      <h1 className="mt-4 text-2xl font-semibold">{content.title}</h1>
      {content.body.map((p) => (
        <p key={p} className="mt-4 text-slate-700">
          {p}
        </p>
      ))}
    </main>
  );
}
