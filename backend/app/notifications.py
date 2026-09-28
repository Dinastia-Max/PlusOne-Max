from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import insert, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NotificationJob, Participation, Slot


REMINDER_OFFSETS = (
    ("reminder_24h", timedelta(hours=24)),
    ("reminder_2h", timedelta(hours=2)),
    ("game_status_1h", timedelta(hours=1)),
)


def schedule_user_notifications(
    session: AsyncSession,
    slot: Slot,
    user_id: int,
    *,
    include_joined: bool,
    now: datetime | None = None,
) -> list[NotificationJob]:
    now = now or datetime.now(timezone.utc)
    event_id = uuid4().hex
    jobs: list[NotificationJob] = []

    if include_joined:
        jobs.append(
            NotificationJob(
                slot_id=slot.id,
                recipient_user_id=user_id,
                notification_type="joined",
                scheduled_at=now,
                dedupe_key=(
                    f"slot:{slot.id}:user:{user_id}:joined:{event_id}"
                ),
            )
        )

    for notification_type, offset in REMINDER_OFFSETS:
        scheduled_at = slot.start_at - offset
        if scheduled_at <= now:
            continue
        jobs.append(
            NotificationJob(
                slot_id=slot.id,
                recipient_user_id=user_id,
                notification_type=notification_type,
                scheduled_at=scheduled_at,
                dedupe_key=(
                    f"slot:{slot.id}:user:{user_id}:"
                    f"{notification_type}:{event_id}"
                ),
            )
        )

    for job in jobs:
        session.add(job)
    return jobs


async def cancel_user_notifications(
    session: AsyncSession,
    slot_id: int,
    user_id: int,
) -> None:
    await session.execute(
        update(NotificationJob)
        .where(
            NotificationJob.slot_id == slot_id,
            NotificationJob.recipient_user_id == user_id,
            NotificationJob.status.in_(("pending", "processing")),
        )
        .values(status="canceled", locked_at=None)
    )


async def schedule_participant_left(
    session: AsyncSession,
    slot_id: int,
    participant_user_id: int,
    *,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    recipient = select(
        literal(slot_id),
        Slot.host_id,
        literal("participant_left"),
        literal(now),
        literal("pending"),
        literal(0),
        literal(
            f"slot:{slot_id}:participant-left:"
            f"{participant_user_id}:{uuid4().hex}"
        ),
    ).where(Slot.id == slot_id)

    await session.execute(
        insert(NotificationJob).from_select(
            [
                "slot_id",
                "recipient_user_id",
                "notification_type",
                "scheduled_at",
                "status",
                "attempts",
                "dedupe_key",
            ],
            recipient,
        )
    )


async def cancel_slot_notifications(
    session: AsyncSession,
    slot_id: int,
) -> None:
    await session.execute(
        update(NotificationJob)
        .where(
            NotificationJob.slot_id == slot_id,
            NotificationJob.status.in_(("pending", "processing")),
        )
        .values(status="canceled", locked_at=None)
    )


async def schedule_slot_canceled(
    session: AsyncSession,
    slot_id: int,
    *,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    recipients = select(
        literal(slot_id),
        Participation.user_id,
        literal("slot_canceled"),
        literal(now),
        literal("pending"),
        literal(0),
    ).where(Participation.slot_id == slot_id)

    await session.execute(
        insert(NotificationJob).from_select(
            [
                "slot_id",
                "recipient_user_id",
                "notification_type",
                "scheduled_at",
                "status",
                "attempts",
            ],
            recipients,
        )
    )
