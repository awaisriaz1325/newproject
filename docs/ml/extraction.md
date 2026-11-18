# ML spec: document extraction

**Goal:** turn redacted page text/images into versioned structured data (`compback_extract.schemas`,
`SCHEMA_VERSION = 2026-11-18.v1`) with page citations and per-field confidence.

**Extractors**
- `heuristic-v1` (baseline, deterministic, no network) — premium audits only.
- `claude-opus-5-5` via `AnthropicExtractor` (structured outputs, redacted page images + text). Not run in
  this environment: no API key, and spending on a paid API needs founder approval (FD-06).

**Routing to humans:** an extraction is `needs_review` when any field confidence < 0.9, an arithmetic
cross-check fails, no class lines are found, the LLM refused or returned invalid output, the per-org
LLM cost cap is reached, or the document mentions an out-of-scope arrangement (PEO, self-insured,
retrospective rating, large deductible). Edits are stored in `extraction_edits` as evaluation data
(usable for training/eval only with the customer's `evaluation_data` consent).

**Evaluation (real runs, synthetic corpus, 60 documents each):**

| Corpus | class_lines recall | class_lines precision | scalar fields recall | s/doc |
|---|---|---|---|---|
| Native text layer (`extraction-eval-native.md`) | 1.000 | 1.000 | 1.000 | 0.61 |
| Degraded scans, OCR path (`extraction-eval-scanned.md`) | 0.687 | 1.000 | 0.983–1.000 | 1.25 |

Interpretation: the baseline is reliable on clean digital PDFs from our own synthetic layouts and
**misses ~31% of class lines on noisy scans** (mostly the "statement" layout, where OCR merges table
columns). Precision stays ~1.0, so misses become review work, not wrong numbers. These are synthetic
results and say nothing about real carrier documents. Next: run the same harness with the Claude
extractor once FD-06 is approved, and build a consented real-document set.

**Prompt-injection defence:** see `packages/extract/tests/test_extract.py` (document text never in the
system prompt; injected values caught by arithmetic checks; heuristic results stable under injected text).
