"""Routes utilisateur : profil, onboarding, gestion du compte."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.users.models import User
from app.users.schemas import (
    OnboardingRequest,
    OnboardingResponse,
    UpdateProfileRequest,
    UserProfileResponse,
)
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile", response_model=UserProfileResponse, summary="Get user profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    return UserProfileResponse.model_validate(current_user)


@router.put("/profile", response_model=UserProfileResponse, summary="Update user profile")
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    updated = await UserService.update_profile(db, current_user, payload)
    return UserProfileResponse.model_validate(updated)


@router.post(
    "/onboarding",
    response_model=OnboardingResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete user onboarding",
)
async def complete_onboarding(
    payload: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingResponse:
    updated = await UserService.complete_onboarding(db, current_user, payload)
    return OnboardingResponse.model_validate(updated)


@router.delete(
    "/account",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Soft delete user account",
)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await UserService.soft_delete_account(db, current_user)
