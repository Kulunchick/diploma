"""SQLAlchemy 2.0 ORM models for the persistent information system.

Every user owns their own services, providers, planning cells and formation
results — there is no sharing between users in this iteration, so most tables
carry an ``owner_id`` FK to ``users`` and all list queries filter by it.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.operations.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class Service(TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_services_owner_name"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    groups: Mapped[list["ServiceGroup"]] = relationship(
        secondary="service_group_members", back_populates="members", viewonly=True
    )


class ServiceGroup(TimestampMixin, Base):
    __tablename__ = "service_groups"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_service_groups_owner_name"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    members: Mapped[list[Service]] = relationship(
        secondary="service_group_members", back_populates="groups"
    )


class ServiceGroupMember(Base):
    __tablename__ = "service_group_members"
    # A service belongs to at most one group (enables all-or-nothing aggregation).
    __table_args__ = (
        UniqueConstraint("service_id", name="uq_service_group_members_service_id"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_groups.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), primary_key=True
    )


class Provider(TimestampMixin, Base):
    __tablename__ = "providers"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_providers_owner_name"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class PlanningCell(TimestampMixin, Base):
    """Planning data for one (service, provider) pair.

    ``price`` = preferential price d_ij, ``resource`` = IT-company resource
    usage β_ij, ``provider_revenue`` = provider expected revenue p_ij,
    ``discount`` = r_ij. Only price, resource and discount feed the solver;
    provider_revenue is stored for the future combined method.
    """

    __tablename__ = "planning_cells"
    __table_args__ = (
        UniqueConstraint("service_id", "provider_id", name="uq_planning_service_provider"),
        CheckConstraint("discount >= 0 AND discount < 1", name="ck_planning_discount"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[float] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    resource: Mapped[float] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    provider_revenue: Mapped[float] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    discount: Mapped[float] = mapped_column(
        Numeric(6, 4), nullable=False, server_default=text("0")
    )


class FormationScenario(TimestampMixin, Base):
    __tablename__ = "formation_scenarios"
    __table_args__ = (
        CheckConstraint(
            "algorithm IN ('probabilistic','ant_colony')", name="ck_formation_algorithm"
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_formation_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    b_total: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    algorithm: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    workflow_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[float | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignments: Mapped[list["FormationAssignment"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    snapshot: Mapped["FormationSnapshot | None"] = relationship(
        back_populates="scenario", cascade="all, delete-orphan", uselist=False
    )


class FormationAssignment(Base):
    """One assigned (service, provider) pair (v_ij = 1) with resolved numbers
    frozen at run time so the result stays reproducible."""

    __tablename__ = "formation_assignments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("formation_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[float] = mapped_column(Numeric(18, 4), nullable=True)
    discount: Mapped[float] = mapped_column(Numeric(6, 4), nullable=True)
    effective_revenue: Mapped[float] = mapped_column(Numeric(18, 4), nullable=True)

    scenario: Mapped[FormationScenario] = relationship(back_populates="assignments")


class FormationIteration(Base):
    """Per-iteration convergence history for a scenario (best objective value
    at each solver iteration). The composite PK doubles as the lookup index."""

    __tablename__ = "formation_iterations"

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("formation_scenarios.id", ondelete="CASCADE"), primary_key=True
    )
    iteration: Mapped[int] = mapped_column(Integer, primary_key=True)
    best_value: Mapped[float] = mapped_column(Double, nullable=False)


class FormationSnapshot(Base):
    """Frozen solver input + ordered id lists so a scenario can be re-run or
    exported later without touching the live catalogue."""

    __tablename__ = "formation_snapshots"

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("formation_scenarios.id", ondelete="CASCADE"), primary_key=True
    )
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    service_order: Mapped[list] = mapped_column(JSONB, nullable=False)
    provider_order: Mapped[list] = mapped_column(JSONB, nullable=False)

    scenario: Mapped[FormationScenario] = relationship(back_populates="snapshot")
