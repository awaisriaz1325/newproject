# ADR-0008: Money representation and rounding

- Status: accepted · Date: 2026-11-18 · Risk: **High** (money)

## Decision
- Python: `decimal.Decimal` only; floats are rejected at type and runtime boundaries (`Money` validators).
- DB: `NUMERIC(14,2)` for currency amounts, `NUMERIC(12,4)` for rates per $100, `NUMERIC(6,4)` for
  factors (experience mod, discount %).
- Rounding: intermediate products are kept at full precision; each **line** is rounded to cents with
  `ROUND_HALF_UP` at the step the source document rounds. A rule may override rounding mode/step and must
  cite the source. When the engine's total and the document's total differ by more than the documented
  tolerance, it is **flagged, never forced**.
- Currency: USD only in v1.

## Consequences
Golden tests assert exact cent values. Property tests check invariants (order independence, zero
findings on consistent documents).
