"""Planning data per (service, provider) pair: prices, resources, provider
revenue and discounts. All routes are owner-scoped.

Deleting a service or provider cascades to its planning cells at the DB level.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.operations.db.base import get_session
from src.operations.db.models import PlanningCell, Provider, Service, User
from src.operations.models.planning import (
    PlanningBulkUpsert,
    PlanningCellRead,
    PlanningCellUpsert,
)
from src.operations.security import get_current_user

router = APIRouter(prefix="/planning", tags=["planning"])


async def _validate_owned(
    cells: list[PlanningCellUpsert], session: AsyncSession, user: User
) -> None:
    """Ensure every referenced service and provider belongs to the user."""
    service_ids = {c.service_id for c in cells}
    provider_ids = {c.provider_id for c in cells}

    if service_ids:
        owned = await session.execute(
            select(Service.id).where(
                Service.id.in_(service_ids), Service.owner_id == user.id
            )
        )
        if set(owned.scalars().all()) != service_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more services do not exist",
            )
    if provider_ids:
        owned = await session.execute(
            select(Provider.id).where(
                Provider.id.in_(provider_ids), Provider.owner_id == user.id
            )
        )
        if set(owned.scalars().all()) != provider_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more providers do not exist",
            )


async def _upsert(cells: list[PlanningCellUpsert], session: AsyncSession, user: User) -> None:
    for cell in cells:
        stmt = pg_insert(PlanningCell).values(
            owner_id=user.id,
            service_id=cell.service_id,
            provider_id=cell.provider_id,
            price=cell.price,
            resource=cell.resource,
            provider_revenue=cell.provider_revenue,
            discount=cell.discount,
            min_value=cell.min_value,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["service_id", "provider_id"],
            set_={
                "price": stmt.excluded.price,
                "resource": stmt.excluded.resource,
                "provider_revenue": stmt.excluded.provider_revenue,
                "discount": stmt.excluded.discount,
                "min_value": stmt.excluded.min_value,
            },
        )
        await session.execute(stmt)


@router.get("", response_model=list[PlanningCellRead])
async def list_planning(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[PlanningCell]:
    result = await session.execute(
        select(PlanningCell).where(PlanningCell.owner_id == user.id)
    )
    return list(result.scalars().all())


@router.put("/cell", response_model=PlanningCellRead)
async def upsert_cell(
    body: PlanningCellUpsert,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> PlanningCell:
    await _validate_owned([body], session, user)
    await _upsert([body], session, user)
    await session.commit()
    result = await session.execute(
        select(PlanningCell).where(
            PlanningCell.service_id == body.service_id,
            PlanningCell.provider_id == body.provider_id,
        )
    )
    return result.scalar_one()


@router.post("/bulk", response_model=list[PlanningCellRead])
async def bulk_upsert(
    body: PlanningBulkUpsert,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[PlanningCell]:
    await _validate_owned(body.cells, session, user)
    await _upsert(body.cells, session, user)
    await session.commit()
    # Return the full, refreshed planning set for the user.
    result = await session.execute(
        select(PlanningCell).where(PlanningCell.owner_id == user.id)
    )
    return list(result.scalars().all())
