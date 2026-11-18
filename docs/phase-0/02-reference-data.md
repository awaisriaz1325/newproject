# Phase 0 — Reference data: class codes and rating rules

> Research date: 2026-11-18. **Risk: High** (licensing/copyright).

## 1. Who publishes rating rules

- **NCCI** administers the Basic Manual, Scopes Manual and Experience Rating Plan for most states.
- **Independent bureau states** (own manuals): California (WCIRB), Delaware (DCRB), Indiana,
  Massachusetts (WCRIBMA), Michigan, Minnesota, New Jersey, New York, North Carolina (NCRB),
  Pennsylvania (PCRB), Wisconsin. NCCI's own exam materials list 10 (omitting WI); the American
  Academy of Actuaries treats WI as independent.
  Sources: [IRMI rating bureaus](https://irmi.com/industries/insurance-industry/rating-statistical-bureaus),
  [AAA issue brief](https://actuary.org/wp-content/uploads/2025/10/casualty-issuebrief-WorkersComp-100725.pdf),
  [DC DISB NCCI exam](https://disb.dc.gov/sites/default/files/dc/sites/disb/publication/attachments/NCCI%20%20Final%20Exam%20as%20of%2012-31-15.pdf).
- **Texas** adopts NCCI items by TDI order (e.g. Item B-1448, payroll inclusions/exclusions,
  effective 2024-01-01). [TDI order](https://www.tdi.texas.gov/rules/2023/documents/b1448order.pdf)

## 2. Licensing / cost

- **NCCI Scopes Manual / Basic Manual:** proprietary, subscription products. We could not find
  public pricing or license terms → `UNVERIFIED`; requires contacting NCCI (founder decision **FD-04**).
- **Publicly available rule text:** several regulators/bureaus publish rule text or filings
  (NCRB's North Carolina Basic Manual online; state insurance department filing PDFs such as
  Missouri's posting of NCCI items B-1420/B-1422; TDI orders). Publicly *viewable* ≠ licensed
  for embedding in a commercial product. **We cite and link; we do not copy or embed manuals.**
- **Decision (build rule §6.1 honored):** the class-code assistant ships behind a
  `ClassificationReferenceProvider` interface with a small, self-authored, clearly-labeled
  placeholder dataset. No scraping of proprietary manuals.

## 3. Rules verified in this pass (seed for the rules registry)

| Rule id | Jurisdiction | Rule | Citation | Status |
|---|---|---|---|---|
| `NC.OT.2C2A` | North Carolina | Overtime: extra pay excluded if records show OT separately by employee and in summary by class. Combined straight+OT at time-and-a-half → exclude **1/3** of total; double time recorded as total → exclude **1/2**; if extra pay recorded separately, exclude all of it. | NCRB NC Basic Manual Rule 2-C-2-a, rev. eff. 2024-01-01 (Circular C-23-6). [NCRB Rule 2](https://www.ncrb.org/digitallibrary/basicmanual/Rule_2_-_Premium_and_Payroll.htm) | **active** (NC only) |
| `NCCI.OT.2B` | NCCI states | Same overtime structure is widely described for NCCI states, but we did not read primary NCCI Basic Manual text. | Secondary only | **candidate** — needs NCCI text |
| `NCCI.EXEC.2E` | NCCI states | Executive officer payroll subject to state min/max on the state pages / Appendix F, applied to average weekly payroll × weeks employed. | Missouri DOI posting of NCCI Item B-1420 [PDF](https://insurance.mo.gov/sites/insurance/files/2024-09/B-1420RevisionstoBasicManualRule2-E-1-BExecutiveOfficersPremiumDetermination2-E-3Partnersand.pdf) | **candidate** — structure only; dollar limits are per state/year and must be loaded per state with citation |
| `NH.EXEC.LIMITS.2024` | New Hampshire | 2024 exec officer min $700/wk, max $5,500/wk | [NH Insurance Dept PDF](https://mm.nh.gov/files/uploads/nhid/documents/minimum-maximum-payroll.pdf) | **candidate** (effective dates need confirming) |

All other rating steps (premium-discount tables, expense constants, state assessments, order of
operations) are **`UNVERIFIED`** and are **not** encoded. In v1, the engine takes the
customer's own document values (rates, mod, discount %, constants) as inputs and verifies the
arithmetic and internal consistency, which needs no external rate data (build prompt §5).

## 4. Founder decisions raised

- **FD-04:** purchase NCCI / bureau manual licenses? (Recommended: **not before first revenue**;
  v1 detectors don't need them. Revisit for class-code assistant v2.)
