# ML spec: class code review assistant (licensing-gated)

- **Goal:** flag assigned class codes that look inconsistent with the employer's described operations,
  as **"needs expert review"** only (never "wrong").
- **Gate (High risk):** reference descriptions come through `ClassificationReferenceProvider`. The only
  provider shipped is `placeholder-v1`: 12 short descriptions written for this project with illustrative
  codes, `licensed_for_production = False`. No bureau manual text is scraped or embedded (FD-04).
- **Baseline:** TF-IDF (1–2 grams) cosine retrieval; flag when the assigned code is outside the top-3.
- **Measured (12 self-written labeled examples, `packages/ml/tests/test_ml.py`):** top-1 recall 0.833,
  top-3 recall 1.000. This tiny set only proves the harness works; it is not evidence of real accuracy.
- **Next:** licensed reference data (FD-04), sentence embeddings + a classifier ranker, a labeled set
  built from reviewer decisions, LLM explanations grounded only in retrieved licensed text.

# ML spec: finding prioritization
`priority_score = midpoint(impact) × confidence × acceptance_prior(detector)` with documented,
hand-set priors (`compback_ml.prioritize`). Replace with a calibrated logistic/GBM model trained on
`outcomes` using time-based validation once enough resolved cases exist.

# ML spec: extraction quality
`compback_ml.quality.edit_rates` computes per-field correction rates by extractor and document type
from `extraction_edits`; rising rates indicate template drift.
