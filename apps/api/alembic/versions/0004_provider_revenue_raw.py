"""recompute provider_value as raw Σ p·v (drop the (1−r) discount factor)

Provider revenue is the provider's income from its own end-clients and does not
depend on the IT-company's discount r. The earlier stored provider_value used
the discounted formula Σ(1−r)·p·v; this recomputes it as the raw Σ p·v for every
completed scenario, from the frozen snapshot (per-service provider_revenue) and
the assignment rows. provider_profit (= Σ(p − (1−r)·d)·v) is unchanged — it was
already correct.

Revision ID: 0004_provider_revenue_raw
Revises: 0003_provider_profit
Create Date: 2026-06-01
"""
import json
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_provider_revenue_raw"
down_revision: Union[str, None] = "0003_provider_profit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_log = logging.getLogger("alembic.runtime.migration")


def _maybe_json(value):
    return json.loads(value) if isinstance(value, str) else value


def upgrade() -> None:
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
            _log.warning("0004: scenario %s has no service_cells; skipped", sid)
            continue

        pidx = {pid: j for j, pid in enumerate(provider_order)}
        rows = conn.execute(
            sa.text(
                "SELECT service_id, provider_id FROM formation_assignments "
                "WHERE scenario_id = :sid"
            ),
            {"sid": sid},
        ).fetchall()

        f_prov = 0.0
        ok = True
        for service_id, provider_id in rows:
            j = pidx.get(str(provider_id))
            sc = service_cells.get(str(service_id))
            if j is None or sc is None:
                ok = False
                break
            prov_rev = sc.get("provider_revenue") or []
            if j >= len(prov_rev):
                ok = False
                break
            f_prov += float(prov_rev[j])  # raw p_ij, no discount

        if not ok:
            _log.warning("0004: scenario %s has unmappable rows; skipped", sid)
            continue

        conn.execute(
            sa.text(
                "UPDATE formation_scenarios SET provider_value = :pv WHERE id = :sid"
            ),
            {"pv": f_prov, "sid": sid},
        )


def downgrade() -> None:
    # Data-only correction; the previous discounted values are not reconstructed.
    pass
