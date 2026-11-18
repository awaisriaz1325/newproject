# Phase 4 report — Extraction + verification

**Built**
- Versioned schemas (premium audit, declarations/quote, experience rating, payroll summary, COI) with
  page + confidence on every value; money as decimal strings → `Decimal`.
- Keyword classifier with out-of-scope detection (PEO, self-insured, retro, large deductible).
- Baseline extractor `heuristic-v1`; `AnthropicExtractor` (Claude structured outputs over redacted
  images + text, refusal/malformed handling, cost accounting); provider chosen by config.
- Arithmetic cross-checks (line = payroll × rate / 100, Σ lines = manual premium, total − billed = balance).
- Pipeline jobs: ingest → classify → extract, with one repair attempt, transient-error retry, per-org LLM
  cost cap, review routing. Tables `extractions`, `extraction_edits` (+ RLS, migration 0006).
- API: get extraction, edit fields (audited, recorded as evaluation data), verify.
- Synthetic generator (fictional, bannered, 3 layouts, 6 injectable error kinds with exact dollar
  effect) and scan degradation; evaluation harness writing `docs/ml/extraction-eval-*.md`.

**Check results (real output):** ruff clean · mypy strict clean (51 files) · **184 passed**, coverage
90% · migrate-check OK. Evaluation numbers in `docs/ml/extraction.md`.

**Deferred:** the side-by-side verification **web UI** is built with the other screens in the web phase
(the API it needs is done). LLM evaluation needs an API key + founder approval (FD-06).
