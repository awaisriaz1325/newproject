# Phase 0 report — Legal, data-source and architecture gate

**Built (docs only, no app code):**
- `docs/phase-0/01-legal-regulatory.md` — licensing findings (NY § 2102(b)(3), VA consultant license, ME, OR, ND/IN), monopolistic states, dispute processes, recommended operating model.
- `docs/phase-0/02-reference-data.md` — bureaus, manual licensing, first verified rule (NC Rule 2-C-2-a overtime), candidates.
- `docs/phase-0/03-providers-and-costs.md` — Claude data retention/ZDR, OCR options, infra cost table.
- ADR-0001…0012, `docs/security/threat-model.md`, `docs/architecture/overview.md` (data flow + ERD, Mermaid).
- `docs/FOUNDER_DECISIONS.md` (FD-01…FD-11).

**Checks:** none applicable (no code).

**Assumptions:** founder approved autonomous progression (ADR-0012); provisional choices listed as FDs.

**Undecided / needs founder:** FD-01 attorney review (blocking launch), FD-06 Anthropic ZDR request, FD-09 brand, FD-10 licensing/partner, FD-11 legal docs.

**Key risk:** In at least NY and VA, being paid to review a policy appears to require a license. The product is built so every state's paid features are **off by default**.
