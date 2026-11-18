"""Extraction evaluation harness: synthetic corpus -> vault page processing -> extractor -> metrics.

Run:  uv run python -m compback_extract.evaluate --n 60 --out docs/ml/extraction-eval.md

Metrics are field-level precision/recall per template. A field counts as correct only when the
extracted value equals ground truth exactly (decimals compared numerically). Results apply to the
*synthetic* corpus only; real-document accuracy must be measured on consented, redacted real data.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from compback_extract.llm import Extractor, HeuristicExtractor, PageInput, extractor_from_settings
from compback_extract.schemas import PremiumAuditV1, to_decimal
from compback_extract.synthetic import corpus, degrade_to_scan, render_pdf
from compback_vault.pages import process_document

SCALARS = [
    "policy_number",
    "total_manual_premium",
    "experience_mod",
    "expense_constant",
    "total_premium",
    "previously_billed",
    "balance",
]


def _eq(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    da, db = to_decimal(a), to_decimal(b)
    if da is not None and db is not None:
        return da == db
    return a.strip() == b.strip()


@dataclass
class Tally:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, predicted: str | None, truth: str | None) -> None:
        if predicted is None and truth is None:
            return
        if predicted is not None and _eq(predicted, truth):
            self.tp += 1
        else:
            if predicted is not None:
                self.fp += 1
            if truth is not None:
                self.fn += 1

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0


@dataclass
class Report:
    extractor: str
    n_docs: int
    by_field: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    by_template: dict[str, Tally] = field(default_factory=lambda: defaultdict(Tally))
    scanned: bool = False
    seconds_per_doc: float = 0.0
    cost_usd: Decimal = Decimal(0)


def score(pred: PremiumAuditV1, truth: PremiumAuditV1, template: str, rep: Report) -> None:
    for name in SCALARS:
        p, t = getattr(pred, name).value, getattr(truth, name).value
        rep.by_field[name].add(p, t)
        rep.by_template[template].add(p, t)
    pred_lines = {(ln.class_code, ln.payroll, ln.rate, ln.premium) for ln in pred.class_lines}
    for ln in truth.class_lines:
        key = (ln.class_code, ln.payroll, ln.rate, ln.premium)
        hit = any(
            k[0] == key[0] and all(_eq(a, b) for a, b in zip(k[1:], key[1:], strict=True))
            for k in pred_lines
        )
        for tally in (rep.by_field["class_lines"], rep.by_template[template]):
            if hit:
                tally.tp += 1
            else:
                tally.fn += 1
    extra = max(0, len(pred.class_lines) - len(truth.class_lines))
    rep.by_field["class_lines"].fp += extra
    rep.by_template[template].fp += extra


def run(n: int, extractor: Extractor, scanned: bool = False) -> Report:
    rep = Report(extractor=extractor.name, n_docs=n, scanned=scanned)
    started = time.perf_counter()
    for i, case in enumerate(corpus(n)):
        pdf = render_pdf(case)
        if scanned:
            pdf = degrade_to_scan(pdf, seed=i)
        result = process_document(pdf, "pdf")
        pages = [PageInput(p.page_no, p.text, p.image_png) for p in result.pages]
        pred, usage = extractor.extract(PremiumAuditV1, "premium_audit", pages)
        rep.cost_usd += usage.cost_usd
        score(pred, case.truth(), case.template, rep)
    rep.seconds_per_doc = (time.perf_counter() - started) / max(n, 1)
    return rep


def to_markdown(rep: Report) -> str:
    def row(name: str, t: Tally) -> str:
        return f"| {name} | {t.precision:.3f} | {t.recall:.3f} | {t.tp} | {t.fp} | {t.fn} |"

    head = "| | precision | recall | TP | FP | FN |\n|---|---|---|---|---|---|"
    lines = [
        "# Extraction evaluation (synthetic corpus"
        + (", degraded scans / OCR path)" if rep.scanned else ", native text layer)"),
        "",
        f"- Generated: {datetime.now(UTC):%Y-%m-%d %H:%M UTC}",
        f"- Extractor: `{rep.extractor}` · documents: {rep.n_docs} · "
        f"mean wall time incl. render+OCR: {rep.seconds_per_doc:.2f} s/doc · "
        f"LLM cost: ${rep.cost_usd:.4f}",
        "- Corpus: `compback_extract.synthetic.corpus` (fictional, 3 layouts, ~50% with injected "
        "errors). **Synthetic only — not a measure of real-world accuracy.**",
        "",
        "## By field",
        head,
        *[row(k, v) for k, v in sorted(rep.by_field.items())],
        "",
        "## By layout",
        head,
        *[row(k, v) for k, v in sorted(rep.by_template.items())],
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--heuristic", action="store_true", help="force the baseline extractor")
    parser.add_argument("--scanned", action="store_true", help="degrade pages to noisy scans")
    args = parser.parse_args()
    extractor = HeuristicExtractor() if args.heuristic else extractor_from_settings()
    rep = run(args.n, extractor, args.scanned)
    md = to_markdown(rep)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md)
        args.out.with_suffix(".json").write_text(
            json.dumps(
                {
                    "extractor": rep.extractor,
                    "n": rep.n_docs,
                    "scanned": rep.scanned,
                    "fields": {k: vars(v) for k, v in rep.by_field.items()},
                    "layouts": {k: vars(v) for k, v in rep.by_template.items()},
                },
                indent=2,
            )
        )
    print(md)  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
