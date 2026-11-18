# Extraction evaluation (synthetic corpus, native text layer)

- Generated: 2026-11-18 12:16 UTC
- Extractor: `heuristic-v1` · documents: 60 · mean wall time incl. render+OCR: 0.60 s/doc · LLM cost: $0.0000
- Corpus: `compback_extract.synthetic.corpus` (fictional, 3 layouts, ~50% with injected errors). **Synthetic only — not a measure of real-world accuracy.**

## By field
| | precision | recall | TP | FP | FN |
|---|---|---|---|---|---|
| balance | 1.000 | 1.000 | 60 | 0 | 0 |
| class_lines | 1.000 | 1.000 | 182 | 0 | 0 |
| expense_constant | 1.000 | 1.000 | 60 | 0 | 0 |
| experience_mod | 1.000 | 1.000 | 60 | 0 | 0 |
| policy_number | 1.000 | 1.000 | 60 | 0 | 0 |
| previously_billed | 1.000 | 1.000 | 60 | 0 | 0 |
| total_manual_premium | 1.000 | 1.000 | 60 | 0 | 0 |
| total_premium | 1.000 | 1.000 | 60 | 0 | 0 |

## By layout
| | precision | recall | TP | FP | FN |
|---|---|---|---|---|---|
| billing | 1.000 | 1.000 | 204 | 0 | 0 |
| statement | 1.000 | 1.000 | 198 | 0 | 0 |
| worksheet | 1.000 | 1.000 | 200 | 0 | 0 |
