import asyncio
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, engine
from app.models import Field, Participation, Slot


FIELDS = (
    {
        "name": "Спортивная площадка Ходынское поле",
        "address": "Ходынский бульвар, 10Б",
        "district": "Хорошёвский",
    },
    {
        "name": "Футбольное поле Динамо",
        "address": "Хорошёвское шоссе, 27",
        "district": "Хорошёвский",
    },
    {
        "name": "Спортивная площадка Берёзовая роща",
        "address": "улица Куусинена, 15",
        "district": "Хорошёвский",
    },
    {
        "name": "Футбольная площадка Песчаная",
        "address": "улица Зорге, 30",
        "district": "Хорошёвский",
    },
)

SLOTS = (
    (91000001, 1, 16, 90, 6, 10, True, 5),
    (91000002, 1, 18, 60, 4, 8, False, 3),
    (91000003, 2, 15, 90, 8, 12, True, 7),
    (91000004, 3, 17, 60, 4, 10, False, 2),
    (91000005, 4, 14, 120, 6, 14, True, 9),
    (91000006, 5, 16, 90, 6, 10, False, 0),
)


async def get_or_create_fields(session: AsyncSession) -> list[Field]:
    fields: list[Field] = []

    for data in FIELDS:
        field = await session.scalar(
            select(Field).where(Field.name == data["name"])
        )
        if field is None:
            field = Field(**data)
            session.add(field)
        else:
            field.address = data["address"]
            field.district = data["district"]
            field.is_active = True
        fields.append(field)

    await session.flush()
    return fields


async def seed_slots(session: AsyncSession, fields: list[Field]) -> None:
    now = datetime.now(timezone.utc)
    first_day = now.date() + timedelta(days=1)

    for index, slot_data in enumerate(SLOTS):
        (
            host_id,
            day_offset,
            start_hour,
            duration_minutes,
            min_players,
            max_players,
            has_ball,
            participants_count,
        ) = slot_data
        start_at = datetime.combine(
            first_day + timedelta(days=day_offset - 1),
            time(hour=start_hour),
            tzinfo=timezone.utc,
        )
        end_at = start_at + timedelta(minutes=duration_minutes)
        field = fields[index % len(fields)]

        slot = await session.scalar(
            select(Slot).where(Slot.host_id == host_id)
        )
        if slot is None:
            slot = Slot(host_id=host_id)
            session.add(slot)

        slot.field_id = field.id
        slot.start_at = start_at
        slot.end_at = end_at
        slot.min_players = min_players
        slot.max_players = max_players
        slot.has_ball = has_ball
        slot.host_contact = f"https://max.ru/u/{host_id}"
        slot.canceled_at = None
        slot.cancel_reason = None
        await session.flush()

        for participant_index in range(participants_count):
            user_id = host_id * 100 + participant_index + 1
            participation = await session.get(
                Participation,
                (slot.id, user_id),
            )
            if participation is None:
                session.add(
                    Participation(
                        slot_id=slot.id,
                        user_id=user_id,
                        brings_ball=participant_index == 0 and not has_ball,
                    )
                )


async def seed() -> None:
    async with SessionLocal() as session:
        fields = await get_or_create_fields(session)
        await seed_slots(session, fields)
        await session.commit()


async def main() -> None:
    try:
        await seed()
        print("Seed data is ready.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
