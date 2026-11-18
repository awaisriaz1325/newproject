# ADR-0014: No server-side model fallback for document extraction

- Status: accepted · Date: 2026-11-18 · Risk: Medium (data handling)

## Context
Anthropic's API can re-run a refused request on a fallback model. Some newer models ("Covered
Models") require 30-day data retention and are not ZDR-eligible.

## Decision
Extraction calls `claude-opus-5-5` without `fallbacks`. A refusal routes the document to the
deterministic baseline plus mandatory human review. This keeps every customer document on a model
whose retention terms we chose and documented.

## Consequences
Rare refusals cost reviewer time instead of an automatic retry on another model.
