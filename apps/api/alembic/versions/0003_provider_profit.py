"""provider_profit column + backfill F_prov / provider_profit for all scenarios

Provider revenue (F_prov) and the new provider_profit are now computed and
stored for every algorithm, not just combined. This adds the column and
backfills both metrics for existing completed scenarios from their frozen
snapshot (per-service provider_revenue + price) and assignment rows (which
pairs are included, and the discount actually applied — final_discount, which
0002 backfilled to the planning discount for the two non-combined methods).

Revision ID: 0003_provider_profit
Revises: 0002_combined_method
Create Date: 2026-06-01
"""
import json
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_provider_profit"
down_revision: Union[str, None] = "0002_combined_method"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_log = logging.getLogger("alembic.runtime.migration")


def _maybe_json(value):
    """JSONB comes back as str from asyncpg; dict from psycopg. Normalise."""
    return json.loads(value) if isinstance(value, str) else value


def upgrade() -> None:
    op.add_column(
        "formation_scenarios",
        sa.Column("provider_profit", sa.Double(), nullable=True),
    )

    conn = op.get_bind()
    scenarios = conn.execute(
        sa.text(
            "SELECT s.id, snap.input_payload, snap.provider_order "
            "FROM formation_scenarios s "
            "JOIN formation_snapshots snap ON snap.scenario_id = s.id "
            "WHERE s.status = 'completed'"
        )
    ).fetchall()

    for sid, payload, provider_order in scenarios:
        payload = _maybe_json(payload) or {}
        provider_order = _maybe_json(provider_order) or []
        service_cells = payload.get("service_cells")
        if not service_cells:
            # Legacy per-service snapshot without provider_revenue — can't
            # recompute; leave both NULL (API renders "—").
            _log.warning("0003 backfill: scenario %s has no service_cells; skipped", sid)
            continue

        pidx = {pid: j for j, pid in enumerate(provider_order)}
        rows = conn.execute(
            sa.text(
                "SELECT service_id, provider_id, price, discount, final_discount "
                "FROM formation_assignments WHERE scenario_id = :sid"
            ),
            {"sid": sid},
        ).fetchall()

        f_prov = 0.0
        provider_profit = 0.0
        ok = True
        for service_id, provider_id, price, discount, final_discount in rows:
            j = pidx.get(str(provider_id))
            sc = service_cells.get(str(service_id))
            if j is None or sc is None:
                ok = False
                break
            prov_rev = sc.get("provider_revenue") or []
            if j >= len(prov_rev):
                ok = False
                break
            p = float(prov_rev[j])
            d = float(price or 0)
            # final_discount holds the negotiated r for combined and the planning
            # r for the others (0002 set it = discount). Fall back to discount.
            r = float(final_discount if final_discount is not None else (discount or 0))
            f_prov += (1.0 - r) * p
            provider_profit += p - (1.0 - r) * d

        if not ok:
            _log.warning("0003 backfill: scenario %s has unmappable rows; skipped", sid)
            continue

        conn.execute(
            sa.text(
                "UPDATE formation_scenarios "
                "SET provider_value = :pv, provider_profit = :pp WHERE id = :sid"
            ),
            {"pv": f_prov, "pp": provider_profit, "sid": sid},
        )


def downgrade() -> None:
    op.drop_column("formation_scenarios", "provider_profit")
