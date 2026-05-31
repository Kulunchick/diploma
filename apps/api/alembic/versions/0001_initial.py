"""initial information-system schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)
_UUID_PK = sa.text("gen_random_uuid()")
_NOW = sa.text("now()")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_PK),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "services",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_PK),
        sa.Column("owner_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("owner_id", "name", name="uq_services_owner_name"),
    )
    op.create_index("ix_services_owner_id", "services", ["owner_id"])

    op.create_table(
        "service_groups",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_PK),
        sa.Column("owner_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("owner_id", "name", name="uq_service_groups_owner_name"),
    )
    op.create_index("ix_service_groups_owner_id", "service_groups", ["owner_id"])

    op.create_table(
        "service_group_members",
        sa.Column(
            "group_id", _UUID,
            sa.ForeignKey("service_groups.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column(
            "service_id", _UUID,
            sa.ForeignKey("services.id", ondelete="CASCADE"), primary_key=True,
        ),
        # A service belongs to at most one group — enables all-or-nothing group
        # aggregation in formation preprocessing.
        sa.UniqueConstraint("service_id", name="uq_service_group_members_service_id"),
    )

    op.create_table(
        "providers",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_PK),
        sa.Column("owner_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("owner_id", "name", name="uq_providers_owner_name"),
    )
    op.create_index("ix_providers_owner_id", "providers", ["owner_id"])

    op.create_table(
        "planning_cells",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_PK),
        sa.Column("owner_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", _UUID, sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", _UUID, sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("resource", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("provider_revenue", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("discount", sa.Numeric(6, 4), nullable=False, server_default=sa.text("0")),
        *_timestamps(),
        sa.UniqueConstraint("service_id", "provider_id", name="uq_planning_service_provider"),
        sa.CheckConstraint("discount >= 0 AND discount < 1", name="ck_planning_discount"),
    )
    op.create_index("ix_planning_cells_owner_id", "planning_cells", ["owner_id"])

    op.create_table(
        "formation_scenarios",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_PK),
        sa.Column("owner_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("b_total", sa.Numeric(18, 4), nullable=False),
        sa.Column("algorithm", sa.Text(), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("workflow_id", sa.Text(), nullable=True),
        sa.Column("value", sa.Double(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "algorithm IN ('probabilistic','ant_colony')", name="ck_formation_algorithm"
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed')", name="ck_formation_status"
        ),
    )
    op.create_index("ix_formation_scenarios_owner_id", "formation_scenarios", ["owner_id"])

    op.create_table(
        "formation_assignments",
        sa.Column("id", _UUID, primary_key=True, server_default=_UUID_PK),
        sa.Column(
            "scenario_id", _UUID,
            sa.ForeignKey("formation_scenarios.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("service_id", _UUID, sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", _UUID, sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
        sa.Column("discount", sa.Numeric(6, 4), nullable=True),
        sa.Column("effective_revenue", sa.Numeric(18, 4), nullable=True),
    )
    op.create_index("ix_formation_assignments_scenario_id", "formation_assignments", ["scenario_id"])

    op.create_table(
        "formation_iterations",
        sa.Column(
            "scenario_id", _UUID,
            sa.ForeignKey("formation_scenarios.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("iteration", sa.Integer(), primary_key=True),
        sa.Column("best_value", sa.Double(), nullable=False),
    )

    op.create_table(
        "formation_snapshots",
        sa.Column(
            "scenario_id", _UUID,
            sa.ForeignKey("formation_scenarios.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False),
        sa.Column("service_order", postgresql.JSONB(), nullable=False),
        sa.Column("provider_order", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("formation_snapshots")
    op.drop_table("formation_iterations")
    op.drop_table("formation_assignments")
    op.drop_table("formation_scenarios")
    op.drop_table("planning_cells")
    op.drop_table("providers")
    op.drop_table("service_group_members")
    op.drop_table("service_groups")
    op.drop_table("services")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
