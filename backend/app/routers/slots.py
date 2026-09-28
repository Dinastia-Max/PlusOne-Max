from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models import Field, Participation, Slot
from app.notifications import (
    cancel_slot_notifications,
    cancel_user_notifications,
    schedule_participant_left,
    schedule_slot_canceled,
    schedule_user_notifications,
)
from app.schemas import (
    FieldResponse,
    ParticipantResponse,
    SlotCreate,
    SlotDetail,
    SlotListItem,
)


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


def overlapping_slots_query(user_id: int, slot: Slot):
    return (
        select(Slot.id)
        .outerjoin(
            Participation,
            and_(
                Participation.slot_id == Slot.id,
                Participation.user_id == user_id,
            ),
        )
        .where(
            Slot.id != slot.id,
            Slot.canceled_at.is_(None),
            or_(Slot.host_id == user_id, Participation.user_id == user_id),
            Slot.start_at < slot.end_at,
            Slot.end_at > slot.start_at,
        )
        .limit(1)
    )


@router.post("", response_model=SlotDetail, status_code=status.HTTP_201_CREATED)
async def create_slot(
    slot_data_in: SlotCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> SlotDetail:
    if slot_data_in.start_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Slot must start in the future",
        )

    async with session.begin():
        result = await session.execute(
            select(Field).where(
                Field.id == slot_data_in.field_id,
                Field.is_active.is_(True),
            )
        )
        field = result.scalar_one_or_none()
        if field is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active field not found",
            )

        slot = Slot(
            field_id=slot_data_in.field_id,
            host_id=user_id,
            start_at=slot_data_in.start_at,
            end_at=slot_data_in.end_at,
            min_players=slot_data_in.min_players,
            max_players=slot_data_in.max_players,
            has_ball=slot_data_in.has_ball,
        )
        session.add(slot)
        await session.flush()
        schedule_user_notifications(
            session,
            slot,
            user_id,
            include_joined=False,
        )

    return SlotDetail(
        **slot_data(slot, field, participants_count=0),
        min_players=slot.min_players,
        host_id=slot.host_id,
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


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_slot(
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
        if slot.host_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the host can cancel this slot",
            )
        if slot.canceled_at is None:
            slot.canceled_at = datetime.now(timezone.utc)
            await cancel_slot_notifications(session, slot.id)
            await schedule_slot_canceled(session, slot.id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{slot_id}/join", status_code=status.HTTP_204_NO_CONTENT)
async def join_slot(
    slot_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> Response:
    async with session.begin():
        await session.scalar(select(func.pg_advisory_xact_lock(user_id)))

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

        overlapping_slot_id = await session.scalar(
            overlapping_slots_query(user_id, slot)
        )
        if overlapping_slot_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User has an overlapping slot",
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
        schedule_user_notifications(
            session,
            slot,
            user_id,
            include_joined=True,
            now=now,
        )

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
        await cancel_user_notifications(session, slot_id, user_id)
        await schedule_participant_left(session, slot_id, user_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{slot_id}/participants",
    response_model=list[ParticipantResponse],
)
async def get_slot_participants(
    slot_id: int,
    session: AsyncSession = Depends(get_db),
) -> list[ParticipantResponse]:
    slot_exists = await session.scalar(
        select(Slot.id).where(
            Slot.id == slot_id,
            Slot.canceled_at.is_(None),
        )
    )
    if slot_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found",
        )

    result = await session.scalars(
        select(Participation)
        .where(Participation.slot_id == slot_id)
        .order_by(Participation.joined_at, Participation.user_id)
    )
    return [
        ParticipantResponse.model_validate(participation)
        for participation in result.all()
    ]
