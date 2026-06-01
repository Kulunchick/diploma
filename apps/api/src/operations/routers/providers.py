"""Provider directory CRUD. All routes are owner-scoped."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.operations.db.base import get_session
from src.operations.db.models import Provider, User
from src.operations.models.provider import ProviderCreate, ProviderRead, ProviderUpdate
from src.operations.security import get_current_user

router = APIRouter(prefix="/providers", tags=["providers"])


async def _get_owned(
    provider_id: uuid.UUID, session: AsyncSession, user: User
) -> Provider:
    result = await session.execute(
        select(Provider).where(Provider.id == provider_id, Provider.owner_id == user.id)
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return provider


@router.get("", response_model=list[ProviderRead])
async def list_providers(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[Provider]:
    result = await session.execute(
        select(Provider).where(Provider.owner_id == user.id).order_by(Provider.name)
    )
    return list(result.scalars().all())


@router.post("", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(
    body: ProviderCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Provider:
    provider = Provider(owner_id=user.id, name=body.name, description=body.description)
    session.add(provider)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A provider with this name already exists",
        )
    await session.refresh(provider)
    return provider


@router.get("/{provider_id}", response_model=ProviderRead)
async def get_provider(
    provider_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Provider:
    return await _get_owned(provider_id, session, user)


@router.put("/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: uuid.UUID,
    body: ProviderUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Provider:
    provider = await _get_owned(provider_id, session, user)
    provider.name = body.name
    provider.description = body.description
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A provider with this name already exists",
        )
    await session.refresh(provider)
    return provider


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    provider = await _get_owned(provider_id, session, user)
    await session.delete(provider)
    await session.commit()
