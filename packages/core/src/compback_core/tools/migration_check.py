"""CI check: migrations round-trip and the ORM models match the migrated schema.

Runs upgrade head -> downgrade base -> upgrade head against COMPBACK_DATABASE_OWNER_URL, then
uses Alembic's autogenerate comparison. Any diff fails the build (models and migrations drifted).
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, pool

from compback_core.config import get_settings
from compback_core.models import Base


def _config() -> Config:
    root = Path(__file__).resolve().parents[5]
    return Config(str(root / "alembic.ini"))


def main() -> int:
    cfg = _config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(
        get_settings().database_owner_url.get_secret_value(), poolclass=pool.NullPool
    )
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    if diff:
        for item in diff:
            print(f"DRIFT: {item}", file=sys.stderr)  # noqa: T201 - CLI output
        return 1
    print("migrations OK: round-trip passed, no model drift")  # noqa: T201 - CLI output
    return 0


if __name__ == "__main__":
    sys.exit(main())
