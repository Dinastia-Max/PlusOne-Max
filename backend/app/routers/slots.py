from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Field, Participation, Slot
from app.schemas import FieldResponse, SlotDetail, SlotListItem


router = APIRouter(prefix="/slots", tags=["slots"])


def slot_data(
    slot: Slot,
    field: Field,
    participants_count: int,
) -> dict:
    return {
        "id": slot.id,
        "start_at": slot.start_at,
        "end_at": slot.end_at,
        "max_players": slot.max_players,
        "participants_count": participants_count,
        "has_ball": slot.has_ball,
        "field": FieldResponse.model_validate(field),
    }


def slots_query():
    participants_count = func.count(Participation.user_id).label(
        "participants_count"
    )

    return (
        select(Slot, Field, participants_count)
        .join(Field, Field.id == Slot.field_id)
        .outerjoin(Participation, Participation.slot_id == Slot.id)
        .where(Slot.canceled_at.is_(None))
        .group_by(Slot.id, Field.id)
    )


@router.get("", response_model=list[SlotListItem])
async def get_slots(
    session: AsyncSession = Depends(get_db),
) -> list[SlotListItem]:
    now = datetime.now(timezone.utc)
    week_later = now + timedelta(days=7)

    result = await session.execute(
        slots_query()
        .where(Slot.start_at >= now, Slot.start_at <= week_later)
        .order_by(Slot.start_at)
    )

    return [
        SlotListItem(**slot_data(slot, field, participants_count))
        for slot, field, participants_count in result.all()
    ]


@router.get("/{slot_id}", response_model=SlotDetail)
async def get_slot(
    slot_id: int,
    session: AsyncSession = Depends(get_db),
) -> SlotDetail:
    result = await session.execute(
        slots_query().where(Slot.id == slot_id)
    )
    row = result.one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found",
        )

    slot, field, participants_count = row
    return SlotDetail(
        **slot_data(slot, field, participants_count),
        min_players=slot.min_players,
        host_id=slot.host_id,
    )
