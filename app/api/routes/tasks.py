"""Task management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.plan import FocusSessionStart, TaskTransitionPayload
from app.services.plan_service import get_day_snapshot, log_focus_session, transition_task

router = APIRouter(prefix="/task", tags=["task"])


@router.get("/next")
async def next_task(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    snapshot = await get_day_snapshot(session, user)
    pending = [task for task in snapshot.tasks if task.status in {"todo", "doing"}]
    return pending[0] if pending else None


@router.post("/{task_id}/transition")
async def transition(
    payload: TaskTransitionPayload,
    task_id: int = Path(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        task = await transition_task(session, user, task_id, payload)
        await session.commit()
        return {"task_id": task.id, "status": task.status}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/focus")
async def start_focus(
    payload: FocusSessionStart,
    task_id: int = Path(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    session_obj = await log_focus_session(session, user, task_id, payload.minutes)
    await session.commit()
    return {"id": session_obj.id, "minutes": session_obj.minutes}
