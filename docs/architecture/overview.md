# Architecture overview

## Data flow

```mermaid
flowchart LR
  U[Employer / Advisor browser] -->|TLS, session cookie| W[Next.js web]
  W -->|REST JSON| A[FastAPI API]
  A -->|RLS: app.org_id| DB[(PostgreSQL)]
  A -->|presigned PUT/GET, short TTL| S3[(Object storage: R2, SSE)]
  A -->|enqueue in same tx| DB
  WK[Worker] -->|SKIP LOCKED jobs| DB
  WK -->|read original| S3
  WK --> AV[ClamAV]
  WK --> OCR[Tesseract local OCR]
  OCR --> RED[SSN/TIN redaction: text + pixels]
  RED -->|redacted pages only| LLM[Claude API - ZDR]
  LLM -->|schema-validated JSON| WK
  WK --> ENG[Rating engine - Decimal, deterministic]
  ENG --> DB
  R[Reviewer console - MFA, JIT] --> A
  A --> ST[Stripe - invoices]
  ST -->|signed webhooks| A
  KMS[KMS master key] -.wraps data keys.-> A
  KMS -.-> WK
```

No path from the platform to any carrier exists in v1.

## ERD (core)

```mermaid
erDiagram
  organizations ||--o{ memberships : has
  users ||--o{ memberships : has
  organizations ||--o{ advisor_client_links : "advisor side"
  organizations ||--o{ advisor_client_links : "client side"
  organizations ||--|| employers : "employer profile"
  employers ||--o{ policies : holds
  policies ||--o{ documents : evidences
  documents ||--o{ extractions : produces
  policies ||--o{ class_assignments : has
  policies ||--o{ rating_inputs : verified
  rating_inputs ||--o{ recomputations : feeds
  rating_rules ||--o{ findings : cites
  recomputations ||--o{ findings : yields
  policies ||--o{ cases : disputes
  cases ||--o{ dispute_packages : versions
  cases ||--o{ outcomes : results
  cases ||--o{ fees : bills
  organizations ||--o{ audit_log : records
  organizations ||--o{ consents : grants
  organizations ||--o{ jobs : queues
  jurisdiction_policies ||--o{ policies : governs
```

Every tenant table has `org_id NOT NULL`, RLS `FORCE`d, and an index leading with `org_id`.
