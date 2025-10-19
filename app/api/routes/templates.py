"""Plan templates endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.deps import get_current_user, get_db
from app.models.plan import PlanTemplate
from app.models.user import User
from app.schemas.plan import PlanTemplatePayload
from app.services.plan_service import ensure_default_templates, upsert_template

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
async def list_templates(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    await ensure_default_templates(session, user)
    result = await session.execute(
        PlanTemplate.__table__.select().where(PlanTemplate.user_id == user.id)
    )
    return result.mappings().all()


@router.post("/upsert")
async def upsert(
    payload: PlanTemplatePayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    template = await upsert_template(session, user, payload)
    await session.commit()
    return {"id": template.id}
