# Extraction evaluation (synthetic corpus, degraded scans / OCR path)

- Generated: 2026-11-18 12:04 UTC
- Extractor: `heuristic-v1` · documents: 60 · mean wall time incl. render+OCR: 1.25 s/doc · LLM cost: $0.0000
- Corpus: `compback_extract.synthetic.corpus` (fictional, 3 layouts, ~50% with injected errors). **Synthetic only — not a measure of real-world accuracy.**

## By field
| | precision | recall | TP | FP | FN |
|---|---|---|---|---|---|
| balance | 1.000 | 0.983 | 59 | 0 | 1 |
| class_lines | 1.000 | 0.687 | 125 | 0 | 57 |
| expense_constant | 1.000 | 0.983 | 59 | 0 | 1 |
| experience_mod | 1.000 | 0.983 | 59 | 0 | 1 |
| policy_number | 1.000 | 1.000 | 60 | 0 | 0 |
| previously_billed | 0.983 | 0.983 | 59 | 1 | 1 |
| total_manual_premium | 1.000 | 0.983 | 59 | 0 | 1 |
| total_premium | 1.000 | 0.983 | 59 | 0 | 1 |

## By layout
| | precision | recall | TP | FP | FN |
|---|---|---|---|---|---|
| billing | 1.000 | 0.971 | 198 | 0 | 6 |
| statement | 0.993 | 0.732 | 145 | 1 | 53 |
| worksheet | 1.000 | 0.980 | 196 | 0 | 4 |
