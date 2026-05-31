"""Service groups — sets of mutually-required services.

Semantics: a group means "if any service from the group is included for a
provider, all services from that group must be included". As per the
architectural constraints, this interdependency is **stored only** in this
iteration — it is surfaced via the API/UI but NOT enforced by the solver
(it will be used later by the combined method). All routes are owner-scoped.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.operations.db.base import get_session
from src.operations.db.models import Service, ServiceGroup, User
from src.operations.models.service_group import (
    ServiceGroupCreate,
    ServiceGroupRead,
    ServiceGroupUpdate,
)
from src.operations.security import get_current_user

router = APIRouter(prefix="/service-groups", tags=["service-groups"])


def _to_read(group: ServiceGroup) -> ServiceGroupRead:
    return ServiceGroupRead(
        id=group.id,
        name=group.name,
        members=[s.id for s in group.members],
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


async def _resolve_members(
    member_ids: list[uuid.UUID], session: AsyncSession, user: User
) -> list[Service]:
    if not member_ids:
        return []
    unique_ids = set(member_ids)
    result = await session.execute(
        select(Service).where(Service.id.in_(unique_ids), Service.owner_id == user.id)
    )
    services = list(result.scalars().all())
    if len(services) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more member services do not exist",
        )
    return services


async def _get_owned(
    group_id: uuid.UUID, session: AsyncSession, user: User
) -> ServiceGroup:
    result = await session.execute(
        select(ServiceGroup)
        .where(ServiceGroup.id == group_id, ServiceGroup.owner_id == user.id)
        .options(selectinload(ServiceGroup.members))
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service group not found")
    return group


@router.get("", response_model=list[ServiceGroupRead])
async def list_service_groups(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ServiceGroupRead]:
    result = await session.execute(
        select(ServiceGroup)
        .where(ServiceGroup.owner_id == user.id)
        .options(selectinload(ServiceGroup.members))
        .order_by(ServiceGroup.name)
    )
    return [_to_read(g) for g in result.scalars().all()]


@router.post("", response_model=ServiceGroupRead, status_code=status.HTTP_201_CREATED)
async def create_service_group(
    body: ServiceGroupCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ServiceGroupRead:
    members = await _resolve_members(body.member_ids, session, user)
    group = ServiceGroup(owner_id=user.id, name=body.name, members=members)
    session.add(group)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service group with this name already exists",
        )
    await session.refresh(group, attribute_names=["members"])
    return _to_read(group)


@router.get("/{group_id}", response_model=ServiceGroupRead)
async def get_service_group(
    group_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ServiceGroupRead:
    return _to_read(await _get_owned(group_id, session, user))


@router.put("/{group_id}", response_model=ServiceGroupRead)
async def update_service_group(
    group_id: uuid.UUID,
    body: ServiceGroupUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ServiceGroupRead:
    group = await _get_owned(group_id, session, user)
    group.name = body.name
    group.members = await _resolve_members(body.member_ids, session, user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service group with this name already exists",
        )
    await session.refresh(group, attribute_names=["members"])
    return _to_read(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_group(
    group_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    group = await _get_owned(group_id, session, user)
    await session.delete(group)
    await session.commit()
