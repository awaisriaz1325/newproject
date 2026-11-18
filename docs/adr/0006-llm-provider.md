# ADR-0006: LLM provider — Claude behind a provider-agnostic adapter

- Status: accepted · Date: 2026-11-18 · Risk: Medium (data handling)

## Decision
`packages/extract` defines `LLMExtractor` protocol; the default implementation uses the official
`anthropic` Python SDK with `claude-opus-5-5`, structured outputs (Pydantic), inline base64 images of
**redacted** pages. Batch API and Files API are **not** used for customer data (not ZDR-eligible per
Anthropic docs). A deterministic `FakeExtractor` backs tests and CI (no network, no cost).

Documents are untrusted input: system prompt + strict JSON schema; document text is never concatenated
into instructions; outputs are validated and cross-checked arithmetically; nothing the LLM returns can
change rules, findings, or numbers without passing the engine.

## Consequences
Founder must request ZDR from Anthropic before production (FD-06).
