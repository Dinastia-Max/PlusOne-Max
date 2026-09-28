from fastapi import APIRouter, Depends
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models import Participation, Slot
from app.routers.slots import slot_data, slots_query
from app.schemas import UserSlotListItem


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/slots", response_model=list[UserSlotListItem])
async def get_current_user_slots(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> list[UserSlotListItem]:
    user_participation = aliased(Participation)
    has_joined = exists(
        select(user_participation.slot_id).where(
            user_participation.slot_id == Slot.id,
            user_participation.user_id == user_id,
        )
    )

    result = await session.execute(
        slots_query()
        .where(or_(Slot.host_id == user_id, has_joined))
        .order_by(Slot.start_at)
    )

    return [
        UserSlotListItem(
            **slot_data(slot, field, participants_count),
            role="host" if slot.host_id == user_id else "participant",
        )
        for slot, field, participants_count in result.all()
    ]
