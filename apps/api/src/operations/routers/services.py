"""Service catalogue CRUD (IT-company side). All routes are owner-scoped."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.operations.db.base import get_session
from src.operations.db.models import Service, User
from src.operations.models.service import ServiceCreate, ServiceRead, ServiceUpdate
from src.operations.security import get_current_user

router = APIRouter(prefix="/services", tags=["services"])


def _to_read(service: Service) -> ServiceRead:
    return ServiceRead(
        id=service.id,
        name=service.name,
        description=service.description,
        group_ids=[g.id for g in service.groups],
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


async def _get_owned(
    service_id: uuid.UUID, session: AsyncSession, user: User
) -> Service:
    result = await session.execute(
        select(Service)
        .where(Service.id == service_id, Service.owner_id == user.id)
        .options(selectinload(Service.groups))
    )
    service = result.scalar_one_or_none()
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


@router.get("", response_model=list[ServiceRead])
async def list_services(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ServiceRead]:
    result = await session.execute(
        select(Service)
        .where(Service.owner_id == user.id)
        .options(selectinload(Service.groups))
        .order_by(Service.name)
    )
    return [_to_read(s) for s in result.scalars().all()]


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(
    body: ServiceCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ServiceRead:
    service = Service(owner_id=user.id, name=body.name, description=body.description)
    session.add(service)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service with this name already exists",
        )
    await session.refresh(service, attribute_names=["groups"])
    return _to_read(service)


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(
    service_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ServiceRead:
    return _to_read(await _get_owned(service_id, session, user))


@router.put("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: uuid.UUID,
    body: ServiceUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ServiceRead:
    service = await _get_owned(service_id, session, user)
    service.name = body.name
    service.description = body.description
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service with this name already exists",
        )
    await session.refresh(service, attribute_names=["groups"])
    return _to_read(service)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    service = await _get_owned(service_id, session, user)
    await session.delete(service)
    await session.commit()
