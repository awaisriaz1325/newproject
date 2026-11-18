# Phase 5 report — Rating engine + rules registry

**Built**
- Rules registry in code with citations, jurisdictions, status (active/candidate/retired) and a
  release-blocking validator (no active rule without a citation). Verified NC rules from the NCRB Basic
  Manual (Rules 2-C-2-a, 2-H, 3-A-1, 3-A-10/18/19); other-state rating rules are candidates.
- Deterministic Decimal engine with line-by-line explanation steps (each tied to a rule), documented
  rounding, what-if overrides for pricing corrections, order-independent input hashing.
- Detectors: line arithmetic, totals, experience-mod vs worksheet, missing promised credit, duplicate
  class lines, payroll vs records, overtime not excluded. Impacts are engine what-ifs (flow through mod
  and percentage schedule credits); ranges where attribution is uncertain; joint estimate prices exact
  corrections together to avoid double counting.
- Finding prioritization baseline (`compback_ml.prioritize`): midpoint × confidence × documented prior.
- Persistence (migration 0007): policies, recomputations (engine + registry version, inputs hash,
  steps), findings (citations, evidence, ranges, reviewer status). RLS on all three.
- API: create policy (monopolistic states declined politely), attach documents, analyze (blocked until
  extractions are verified/ready), latest analysis (customers see only active-rule findings), reviewer
  confirm/reject (candidate findings cannot be confirmed for customers).

**Check results (real output):** ruff clean · mypy strict clean (61 files) · **358 passed**, coverage
91% · migrate-check OK.
- Golden: 40 clean synthetic bills → **zero findings** and exact total reproduction; 6 error kinds × 15
  seeds → all detected; exact kinds priced to the cent, range kinds bracket the injected overcharge;
  mod + credit joint estimate exact; line order shuffles → identical results; 100 Hypothesis bills reconcile.

**Bugs found by tests and fixed:** synthetic generator measured a missing credit against the wrong
baseline; what-if pricing held a percentage schedule credit fixed (overstated impacts); heuristic
extractor did not read schedule credits (would have caused false total mismatches).
