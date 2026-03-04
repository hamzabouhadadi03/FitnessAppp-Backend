"""Agrège tous les routeurs de domaine sous /api/v1."""
from __future__ import annotations

from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.exercises.router import router as exercises_router
from app.gamification.router import router as gamification_router
from app.progression.router import router as progression_router
from app.programs.router import router as programs_router
from app.users.router import router as users_router
from app.workouts.router import router as workouts_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(exercises_router)
api_router.include_router(programs_router)
api_router.include_router(workouts_router)
api_router.include_router(progression_router)
api_router.include_router(gamification_router)
