"""Write a synthetic (fictional) NC audit PDF for local demos and the browser smoke test.

uv run python -m compback_extract.synthetic_cli --out .data/e2e/audit.pdf
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from compback_extract.synthetic import generate_case, render_pdf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(".data/e2e/audit.pdf"))
    parser.add_argument("--seed", type=int, default=77)
    parser.add_argument("--state", default="NC")
    args = parser.parse_args()
    case = generate_case(args.seed, ("mod_mismatch", "line_arithmetic"), "statement")
    case.state = args.state
    case.lines = [replace(ln, state=args.state) for ln in case.lines]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(render_pdf(case))
    print(f"{args.out}: {case.policy_number} {case.period_start}..{case.period_end}")  # noqa: T201


if __name__ == "__main__":
    main()
