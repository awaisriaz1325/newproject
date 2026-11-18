# Rules registry

Source of truth: `packages/rating/src/compback_rating/rules.py` (`REGISTRY_VERSION`). Every
recomputation stores the engine and registry versions it used.

| Rule | Scope | Status | Source |
|---|---|---|---|
| CONS.TOTALS / CONS.MOD / CONS.CREDIT / CONS.PAYROLL / CONS.DUPLICATE | all supported states | active | Internal consistency of the carrier's own documents (no rule interpretation) |
| NC.3A1.LINE — payroll / 100 × rate | NC | active | NCRB NC Basic Manual Rule 3-A-1 (rev. eff. 2024-04-01) |
| NC.3A.ORDER — order of premium elements | NC | active | NCRB NC Basic Manual Rules 3-A-10, 3-A-18, 3-A-19 |
| NC.2C2A.OT — overtime exclusion (1/3, 1/2) | NC | active | NCRB NC Basic Manual Rule 2-C-2-a (rev. eff. 2024-01-01) |
| NC.2H.SUB — uninsured subcontractors | NC | active | NCRB NC Basic Manual Rule 2-H-1, 2-H-2 |
| NC.2E1B.EXEC — executive officer min/max | NC | candidate | Rule 2-E-1-b; limit values (Misc. Values) not loaded |
| NCCI.LINE / NCCI.OT / NCCI.SUB | other states | candidate | `UNVERIFIED` — needs primary NCCI/state text |
| ML.CLASS_REVIEW | all | candidate | never asserted as an error |

**How to promote a candidate:** add a `Citation` (source, section, URL, effective date, retrieved
date) read from the primary document, add golden tests, get expert review, change status to
`active`, bump `REGISTRY_VERSION`, and record the change in the CHANGELOG.

**Consequence today:** outside North Carolina, customer-facing findings come from document
consistency checks (mod vs worksheet, promised credits, payroll vs records, duplicates, totals).
Per-line arithmetic and overtime findings outside NC stay internal ("needs expert") until verified.
