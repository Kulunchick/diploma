"""combined method: min_value, final_discount, provider_value, combined_source

Revision ID: 0002_combined_method
Revises: 0001_initial
Create Date: 2026-05-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_combined_method"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # s_ij — provider's minimum relative-value threshold (constraint (4)).
    op.add_column(
        "planning_cells",
        sa.Column("min_value", sa.Numeric(8, 4), nullable=False, server_default=sa.text("0")),
    )
    op.create_check_constraint("ck_planning_min_value", "planning_cells", "min_value >= 0")

    # The discount actually applied per assignment (negotiated for combined,
    # static for the other two). Backfill existing rows from the static discount.
    op.add_column(
        "formation_assignments",
        sa.Column("final_discount", sa.Numeric(6, 4), nullable=True),
    )
    op.execute("UPDATE formation_assignments SET final_discount = discount")

    # Allow the new 'combined' algorithm.
    op.drop_constraint("ck_formation_algorithm", "formation_scenarios", type_="check")
    op.create_check_constraint(
        "ck_formation_algorithm",
        "formation_scenarios",
        "algorithm IN ('probabilistic','ant_colony','combined')",
    )

    # Combined-method result fields: F_prov and the winning improved candidate.
    op.add_column("formation_scenarios", sa.Column("provider_value", sa.Double(), nullable=True))
    op.add_column("formation_scenarios", sa.Column("combined_source", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_formation_combined_source",
        "formation_scenarios",
        "combined_source IS NULL OR "
        "combined_source IN ('subtask_a_improved','subtask_b_improved')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_formation_combined_source", "formation_scenarios", type_="check")
    op.drop_column("formation_scenarios", "combined_source")
    op.drop_column("formation_scenarios", "provider_value")
    op.drop_constraint("ck_formation_algorithm", "formation_scenarios", type_="check")
    op.create_check_constraint(
        "ck_formation_algorithm",
        "formation_scenarios",
        "algorithm IN ('probabilistic','ant_colony')",
    )
    op.drop_column("formation_assignments", "final_discount")
    op.drop_constraint("ck_planning_min_value", "planning_cells", type_="check")
    op.drop_column("planning_cells", "min_value")
