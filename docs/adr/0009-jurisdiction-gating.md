# ADR-0009: Jurisdiction policy as data, default deny

- Status: accepted · Date: 2026-11-18 · Risk: **High** (legal)

## Decision
A `jurisdiction_policies` table (global, not tenant-scoped) holds per-state flags: `supported`,
`monopolistic`, `free_scan_allowed`, `paid_analysis_allowed`, `contingency_allowed`, `submitter_mode`,
`citation`, `reviewed_by_counsel_at`. Default for every state: free scan allowed only as *educational
arithmetic check*, paid features **disabled** until counsel review. Monopolistic jurisdictions are
declined. New York and Virginia paid analysis are explicitly blocked (verified licensing statutes).

## Consequences
Launching a state is a reviewed data change with an audit-log entry, not a deploy.
