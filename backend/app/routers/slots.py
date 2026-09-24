from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
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


@router.post("/{slot_id}/join", status_code=status.HTTP_204_NO_CONTENT)
async def join_slot(
    slot_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    async with session.begin():
        result = await session.execute(
            select(Slot).where(Slot.id == slot_id).with_for_update()
        )
        slot = result.scalar_one_or_none()

        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Slot not found",
            )

        now = datetime.now(timezone.utc)
        if slot.canceled_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slot is canceled",
            )
        if slot.start_at <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slot has already started",
            )

        result = await session.execute(
            select(Participation).where(
                Participation.slot_id == slot_id,
                Participation.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User has already joined this slot",
            )

        participants_count = await session.scalar(
            select(func.count())
            .select_from(Participation)
            .where(Participation.slot_id == slot_id)
        )
        if (participants_count or 0) >= slot.max_players:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slot is full",
            )

        session.add(Participation(slot_id=slot_id, user_id=user_id))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{slot_id}/join", status_code=status.HTTP_204_NO_CONTENT)
async def leave_slot(
    slot_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    async with session.begin():
        result = await session.execute(
            select(Participation)
            .where(
                Participation.slot_id == slot_id,
                Participation.user_id == user_id,
            )
            .with_for_update()
        )
        participation = result.scalar_one_or_none()

        if participation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Participation not found",
            )

        await session.delete(participation)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
