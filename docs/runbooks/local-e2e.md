# Runbook: local end-to-end browser smoke test

Verified on 2026-11-18: signup → email verification → sign-in → upload → worker processing →
extraction verification → policy → free scan, with screenshots.

```bash
PGHOST=localhost PGUSER=postgres infra/db/create_db.sh compback && make migrate
```

```bash
uv run python -m compback_extract.synthetic_cli --out .data/e2e/audit.pdf
```

```bash
COMPBACK_ENV=dev COMPBACK_COOKIE_SECURE=false COMPBACK_LOCAL_MASTER_KEY_B64=<32 bytes b64> uv run uvicorn compback_api.main:app --port 8000
```

```bash
cd apps/web && pnpm build && pnpm start -p 3000
```

```bash
E2E_OUT_DIR=.data/e2e node tests/e2e/smoke.cjs
```

Screenshots land in `E2E_OUT_DIR` (01-landing … 04-analysis). The worker runs inline via
`E2E_DRAIN_CMD` and needs the same `COMPBACK_*` environment as the API.
