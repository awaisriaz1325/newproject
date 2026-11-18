# Founder decisions

Decisions the build prompt reserves for the founder. Because the founder asked for autonomous
progress (ADR-0012), each has a **PROVISIONAL** choice so work could continue. Nothing provisional
spends money, contacts a third party, or goes live. Review and reply "accept FD-xx" or override.

| ID | Decision | Provisional choice | Why | Risk | Status |
|---|---|---|---|---|---|
| FD-01 | Attorney review of Phase 0 legal summary | **Required before launch.** Product ships with every state's paid features disabled. | NY/VA statutes verified to license fee-based policy review | **High** | OPEN — needs attorney |
| FD-02 | Operating model | Self-help software + advisor channel (licensed brokers/CPAs). No carrier contact in v1. | Lowest regulatory exposure that still sells | High | PROVISIONAL |
| FD-03 | Launch states | None enabled for paid. Research shortlist: FL, GA, TX, AZ, TN, CO (no consultant statute found yet — not clearance). NY, VA blocked. ND/OH/WA/WY declined. | Default deny (ADR-0009) | High | PROVISIONAL |
| FD-04 | Buy NCCI / bureau manuals | **No** until first revenue; v1 detectors use the customer's own documents. | No public pricing; v1 doesn't need them | Medium | PROVISIONAL |
| FD-05 | Fee structure | Free scan; paid full analysis **$499** flat; contingency **25%** of *verified* recovery, credited by the analysis fee, capped at **$25,000** per policy period. All config values, shown to the customer before approval. | Below the 50% market reference; flat fee covers LLM/review cost | Medium | PROVISIONAL (placeholders in config) |
| FD-06 | Request Anthropic ZDR | Yes, before production | Docs: ZDR per-org via sales; Opus 5.5 eligible | Medium | OPEN — founder action |
| FD-07 | Deploy target | Fly.io + Neon + Cloudflare R2 + AWS KMS (≈$45–85/mo est.) | ADR-0007 | Medium | PROVISIONAL |
| FD-08 | Auth: in-house vs hosted (WorkOS/Clerk) | In-house with vetted primitives (argon2id, TOTP), interface allows switch | ADR-0004 | High | PROVISIONAL |
| FD-09 | Brand / domain | "CompBack" working name; no domain purchased; trademark search not done | — | Low | OPEN |
| FD-10 | Licensed partner / own license | Recommend founder explore P&C producer + consultant license in launch states, or a licensed partner | Unlocks NY/VA-type states | High | OPEN |
| FD-11 | Privacy policy / ToS / DPA | Placeholders only, flagged for attorney | Build rule §8 | High | OPEN |
