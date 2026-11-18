"""Seed jurisdiction policies (default deny for paid features; ADR-0009).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-18
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (code, name, monopolistic, free_scan_allowed, notes, citations). Paid analysis and contingency
# are FALSE for every jurisdiction until counsel review (founder decision FD-01 / FD-03).
ROWS: list[tuple[str, str, bool, bool, str, list[str]]] = [
    ('AL', 'Alabama', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('AK', 'Alaska', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('AZ', 'Arizona', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('AR', 'Arkansas', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('CA', 'California', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('CO', 'Colorado', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('CT', 'Connecticut', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('DE', 'Delaware', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('DC', 'District of Columbia', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('FL', 'Florida', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('GA', 'Georgia', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('HI', 'Hawaii', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('ID', 'Idaho', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('IL', 'Illinois', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('IN', 'Indiana', False, True, 'Indiana issues an insurance consultant license; scope vs this activity UNVERIFIED.', ['https://www.in.gov/idoi/licensing/resident-licensing/types-of-resident-licenses/']),
    ('IA', 'Iowa', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('KS', 'Kansas', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('KY', 'Kentucky', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('LA', 'Louisiana', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('ME', 'Maine', False, True, '24-A M.R.S. 1411: fee-based policy advice requires producer or consultant license.', ['https://legislature.maine.gov/statutes/24-A/title24-Asec1411.html']),
    ('MD', 'Maryland', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('MA', 'Massachusetts', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('MI', 'Michigan', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('MN', 'Minnesota', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('MS', 'Mississippi', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('MO', 'Missouri', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('MT', 'Montana', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('NE', 'Nebraska', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('NV', 'Nevada', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('NH', 'New Hampshire', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('NJ', 'New Jersey', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('NM', 'New Mexico', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('NY', 'New York', False, True, 'Paid review/advice on a policy requires an agent, broker or consultant license (Ins. Law 2102(b)(3)). Paid analysis blocked.', ['https://www.dfs.ny.gov/insurance/ogco2008/rg080112.htm']),
    ('NC', 'North Carolina', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('ND', 'North Dakota', True, False, 'Monopolistic state fund: out of scope, declined.', ['https://irmi.com/term/insurance-definitions/state-funds', 'https://www.thehartford.com/workers-compensation/monopolistic-states']),
    ('OH', 'Ohio', True, False, 'Monopolistic state fund: out of scope, declined.', ['https://irmi.com/term/insurance-definitions/state-funds', 'https://www.thehartford.com/workers-compensation/monopolistic-states']),
    ('OK', 'Oklahoma', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('OR', 'Oregon', False, True, 'ORS 744.605 consultant license (UNVERIFIED against official text).', ['https://oregon.public.law/statutes/ors_744.605']),
    ('PA', 'Pennsylvania', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('RI', 'Rhode Island', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('SC', 'South Carolina', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('SD', 'South Dakota', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('TN', 'Tennessee', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('TX', 'Texas', False, True, 'Public adjuster regime appears limited to property loss claims (UNVERIFIED).', ['https://texas.public.law/statutes/tex._ins._code_section_4102.001']),
    ('UT', 'Utah', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('VT', 'Vermont', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('VA', 'Virginia', False, True, 'Fee-based P&C advice requires an insurance consultant license (SCC). Paid analysis blocked.', ['https://www.scc.virginia.gov/regulated-industries/bureau-of-insurance/licensed-agent/insurance-consultants/']),
    ('WA', 'Washington', True, False, 'Monopolistic state fund: out of scope, declined.', ['https://irmi.com/term/insurance-definitions/state-funds', 'https://www.thehartford.com/workers-compensation/monopolistic-states']),
    ('WV', 'West Virginia', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('WI', 'Wisconsin', False, True, 'Not reviewed by counsel. Paid features disabled by default (ADR-0009).', []),
    ('WY', 'Wyoming', True, False, 'Monopolistic state fund: out of scope, declined.', ['https://irmi.com/term/insurance-definitions/state-funds', 'https://www.thehartford.com/workers-compensation/monopolistic-states']),
    ('PR', 'Puerto Rico', True, False, 'Monopolistic state fund: out of scope, declined.', ['https://irmi.com/term/insurance-definitions/state-funds', 'https://www.thehartford.com/workers-compensation/monopolistic-states']),
    ('VI', 'U.S. Virgin Islands', True, False, 'Monopolistic state fund: out of scope, declined.', ['https://irmi.com/term/insurance-definitions/state-funds', 'https://www.thehartford.com/workers-compensation/monopolistic-states']),
]


def upgrade() -> None:
    stmt = sa.text(
        "INSERT INTO jurisdiction_policies (code, name, monopolistic, free_scan_allowed, "
        "paid_analysis_allowed, contingency_allowed, submitter_mode, notes, citations) "
        "VALUES (:code, :name, :mono, :free, false, false, 'customer_only', :notes, "
        "CAST(:cites AS jsonb))"
    )
    for code, name, mono, free, notes, cites in ROWS:
        op.execute(
            stmt.bindparams(
                code=code, name=name, mono=mono, free=free, notes=notes, cites=json.dumps(cites)
            )
        )


def downgrade() -> None:
    op.execute("DELETE FROM jurisdiction_policies")
