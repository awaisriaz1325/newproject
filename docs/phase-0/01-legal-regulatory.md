# Phase 0 — Legal & regulatory findings

> **Risk: High.** This is engineering research, not legal advice. Nothing here may be relied on
> for launch until the founder's attorney reviews it (recorded as founder decision **FD-01**).
> Research date: 2026-11-18.

## 1. The core question

CompBack (a) examines a policyholder's workers' comp policy and premium audit, (b) recomputes
premium and identifies overcharges, (c) drafts a dispute package, and (d) charges a fee (flat
and/or contingency on recovery). In several states, **receiving a fee for examining or evaluating
an insurance policy, or for advising on one, is itself a licensed activity** — independent of
who submits the dispute.

## 2. Verified findings (primary or regulator sources)

| State | Finding | Source | Status |
|---|---|---|---|
| **New York** | Ins. Law § 2102(b)(3): unless licensed as an agent, broker or consultant, no person "shall receive any money, fee, commission or thing of value for examining, appraising, reviewing or evaluating any insurance policy … or shall make recommendations or give advice with regard to any of the above." DFS OGC opinions apply this to nonresident, fee-based reviewers delivering reports by email/website. Violation is a misdemeanor (§ 109(a)). | [NY DFS OGC Op. 08-01-12](https://www.dfs.ny.gov/insurance/ogco2008/rg080112.htm), [Op. 05-01-03](https://www.dfs.ny.gov/insurance/ogco2005/rg050103.htm), [Op. 07-03-04](https://www.dfs.ny.gov/insurance/ogco2007/rg070304.htm) | **Verified — CompBack's paid analysis is very likely a licensed activity in NY.** |
| **Virginia** | SCC: "any individual or agency who charges a fee to advise in Life and Health or Property and Casualty insurance" must hold an insurance consultant license; written contract required before consulting. Exempt: attorneys acting professionally, CPAs and actuaries consulting in the normal course, employed risk managers, commission-only producers. | [Virginia SCC — Insurance Consultants](https://www.scc.virginia.gov/regulated-industries/bureau-of-insurance/licensed-agent/insurance-consultants/), [Va. Code Title 38.2 Ch. 18 Art. 4](https://law.lis.virginia.gov/vacodefull/title38.2/chapter18/article4/) | **Verified (regulator page).** |
| **Maine** | 24-A M.R.S. § 1411: fee-based advice on a policy's benefits/disadvantages requires a producer or consultant license. | [Maine 24-A §1411](https://legislature.maine.gov/statutes/24-A/title24-Asec1411.html) | Verified (statute site, via search excerpt). |
| **Oregon** | ORS 744.605: may not engage in business as an insurance consultant without a DCBS license. | [ORS 744.605](https://oregon.public.law/statutes/ors_744.605) | Secondary host of statute — `UNVERIFIED` against oregonlegislature.gov. |
| **North Dakota / Indiana** | Both issue consultant licenses (ND by exam per line; IN consultant license is exclusive of producer license). ND is also monopolistic (out of scope). | [ND Insurance Dept — Consultant](https://www.insurance.nd.gov/producers/other-licenses/consultant), [IDOI license types](https://www.in.gov/idoi/licensing/resident-licensing/types-of-resident-licenses/) | Verified that licenses exist; scope vs. CompBack's activity `UNVERIFIED`. |
| **Texas** | Public insurance adjuster (Ins. Code ch. 4102) is defined around claims "for loss or damage under any policy of insurance covering real or personal property." A premium audit dispute is not a property loss claim, so the PA regime **appears** not to apply. | [Tex. Ins. Code §4102.001](https://texas.public.law/statutes/tex._ins._code_section_4102.001), [TDI bulletin](https://www.tdi.texas.gov/bulletins/2008/cc46.html) | `UNVERIFIED` — secondary source text; attorney must confirm. |
| **Florida** | Public adjuster statute (§626.854) ties compensation to "claim payments or settlements"; definition not retrieved. | [Fla. Stat. 626.854](https://www.flsenate.gov/Laws/statutes/2021/626.854) | `UNVERIFIED`. |
| **NAIC (general)** | "Not all states require a separate consultant license"; in those, a producer license plus consultant disclosure rules may apply; some states bar holding both licenses. | [NAIC State Licensing Handbook](https://content.naic.org/sites/default/files/inline-files/State%20Licensing%20Handbook%20-%20Complete%20and%20Final.pdf) | Verified (NAIC). Full state list `UNVERIFIED`. |

## 3. Monopolistic state funds (out of scope)

**North Dakota, Ohio, Washington, Wyoming** (plus Puerto Rico and USVI). Sources consistently agree
([IRMI](https://irmi.com/term/insurance-definitions/state-funds), [The Hartford](https://www.thehartford.com/workers-compensation/monopolistic-states),
[Insureon](https://insureon.com/small-business-insurance/workers-compensation/monopolistic-workers-comp-states)).
Nevada (1999) and West Virginia (2008) opened their markets. Status: carrier/industry sources, not
regulator primary sources → treated as **verified enough to decline** (declining is the safe direction).
Encoded in `packages/core` as `MONOPOLISTIC_JURISDICTIONS` with these citations.

## 4. Dispute processes (where a policyholder goes)

- **NCCI states:** policyholder first raises it with the carrier; if unresolved, NCCI's Dispute
  Resolution Process may apply (Regulatory Services Manager; hearing if unresolved); state
  administrative review is also available and in some states de novo.
  Sources: [CT Insurance Dept — WC Dispute Resolution](https://portal.ct.gov/cid/resource-library/wc-dispute-resolution),
  [TX TDI notice B-1432](https://www.tdi.texas.gov/rules/2016/documents/noticeb1432.pdf),
  [NH Insurance Dept decisions](https://mm.nh.gov/files/uploads/nhid/documents/engineering-services-final-decision-and-order.pdf).
- **Oregon:** OAR 836-043-0071 defines a bona fide premium dispute (written notice; employer's
  estimate of correct premium with explanation). [Cornell LII](https://www.law.cornell.edu/regulations/oregon/Or-Admin-Code-SS-836-043-0071)
- **Tennessee:** published procedure for premium disputes (PDF returned 403 to our fetcher —
  content `UNVERIFIED`). [TN Commerce & Insurance](https://www.tn.gov/content/dam/tn/commerce/documents/insurance/policy-wc/WCAddressingPremiumDisputes_20260401.pdf)
- **North Carolina:** Basic Manual Rule 6 — Dispute Resolution and Appeals. [NCRB](https://www.ncrb.org/digitallibrary/basicmanual/Rule_6_-_Dispute_Resolution_and_Appeals_Process.htm)
- **Deadlines:** NH applied a three-year limit in one appeal; no general deadline is verified. Per
  build rules, **the product shows "unknown — check your policy/notice"** unless a cited deadline
  exists in the registry.

## 5. Contingency fees

Market practice (vendor marketing only — not legal authority): many recovery firms work on
contingency, one advertising 50% of recovered premium ([wcauditrecovery.com](https://wcauditrecovery.com/)).
Whether contingency fees for this activity are capped or barred in any state is `UNVERIFIED`.
Public-adjuster fee caps (e.g. Florida) likely do not apply to premium disputes — `UNVERIFIED`.

## 6. Recommended operating model (engineering recommendation, attorney to confirm)

**Risk: High.** Recommended v1 model, in order of safety:

1. **Per-state gating, default deny.** Every US jurisdiction gets a `jurisdiction_policy` row with
   `analysis_allowed`, `paid_analysis_allowed`, `contingency_allowed`, `submitter_mode`
   (`customer_only` | `customer_or_own_advisor` | `licensed_partner`), and a citation. Default for
   every state is **blocked** until counsel marks it cleared. Implemented in Phase 2 as data.
2. **Hard-block New York and Virginia for paid analysis** (verified licensing statutes) unless a
   licensed partner or the founder's own consultant/producer license covers it. Maine, Oregon,
   Indiana, North Dakota: blocked pending counsel.
3. **Self-help software positioning:** customer uploads, software computes, customer (or their own
   broker/CPA) decides and submits. CompBack never contacts carriers in v1 (already a build rule).
4. **Advisor channel (B2B2B):** licensed brokers/consultants/CPAs use CompBack as a tool for their
   clients. Note Virginia's CPA/actuary exemption — a CPA-channel launch may be the lowest-risk
   path in consultant-licensing states (`UNVERIFIED` per state).
5. **Longer-term:** founder (or an entity) obtains a P&C producer and/or consultant license in
   launch states, or partners with a licensed firm (fee-sharing rules `UNVERIFIED`).

**Launch-state shortlist (to research next with counsel):** large NCCI states where we found **no**
consultant-licensing statute in this pass and that are not monopolistic — e.g. Florida, Georgia,
Texas, Arizona, Tennessee, Colorado. Absence of evidence is **not** clearance. Each needs counsel sign-off.

## 7. Privacy law touchpoints (`UNVERIFIED`, counsel to confirm)

- State data-breach notification laws apply in all 50 states to SSNs/financial data — a further
  reason we **never persist SSNs** (redacted at ingest).
- Comprehensive state privacy laws (e.g. CCPA/CPRA) often have revenue/volume thresholds and
  B2B nuances; payroll registers contain employee personal data → treat CompBack as a
  **service provider/processor** to the employer, with a DPA. Placeholder only.
- GLBA: CompBack is not a financial institution under our reading; `UNVERIFIED`.

## 8. What is undecided

Everything in §6 requires attorney review. We built the product so that the answer is
configuration (jurisdiction policy table), not code.
