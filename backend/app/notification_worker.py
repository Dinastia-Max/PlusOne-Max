import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot import MaxBot
from app.config import get_settings
from app.database import SessionLocal
from app.models import Field, NotificationJob, Participation, Slot


MOSCOW_TZ = ZoneInfo("Europe/Moscow")
SendText = Callable[[int, str], Awaitable[None]]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("plusone.notification_worker")


class NotificationRenderError(ValueError):
    pass


def slot_summary(slot: Slot, field: Field) -> str:
    start = slot.start_at.astimezone(MOSCOW_TZ)
    end = slot.end_at.astimezone(MOSCOW_TZ)
    return (
        f"{start:%d.%m.%Y}, {start:%H:%M}–{end:%H:%M}\n"
        f"{field.name}, {field.address}"
    )


async def render_notification(
    session: AsyncSession,
    job: NotificationJob,
) -> str:
    participants_count = func.count(Participation.user_id).label(
        "participants_count"
    )
    result = await session.execute(
        select(Slot, Field, participants_count)
        .join(Field, Field.id == Slot.field_id)
        .outerjoin(Participation, Participation.slot_id == Slot.id)
        .where(Slot.id == job.slot_id)
        .group_by(Slot.id, Field.id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotificationRenderError("Slot not found")

    slot, field, player_count = row
    summary = slot_summary(slot, field)
    payload = job.payload if isinstance(job.payload, dict) else {}

    if job.notification_type == "joined":
        return f"Вы записаны на игру.\n\n{summary}"
    if job.notification_type == "reminder_24h":
        return f"Завтра игра.\n\n{summary}"
    if job.notification_type == "reminder_2h":
        return f"Напоминание: игра через 2 часа.\n\n{summary}"
    if job.notification_type == "game_status_1h":
        if slot.canceled_at is not None:
            return f"Игра отменена.\n\n{summary}"
        if player_count >= slot.min_players:
            return f"Игра подтверждена — минимум участников набран.\n\n{summary}"
        missing = slot.min_players - player_count
        return f"До игры час. Не хватает игроков: {missing}.\n\n{summary}"
    if job.notification_type == "slot_canceled":
        reason = payload.get("reason") or slot.cancel_reason
        suffix = f"\nПричина: {reason}" if reason else ""
        return f"Игра отменена хостом.\n\n{summary}{suffix}"
    if job.notification_type == "slot_changed":
        return f"Хост изменил время или поле игры.\n\n{summary}"
    if job.notification_type == "host_message":
        message = str(payload.get("message") or "").strip()
        if not message:
            raise NotificationRenderError("Host message is empty")
        return f"Сообщение от хоста:\n{message}\n\n{summary}"
    if job.notification_type == "participant_left":
        participant = str(payload.get("participant_name") or "Участник")
        return f"{participant} отказался от игры, освободилось место.\n\n{summary}"

    raise NotificationRenderError(
        f"Unknown notification type: {job.notification_type}"
    )


class NotificationWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        send_text: SendText,
        *,
        batch_size: int = 50,
        max_attempts: int = 5,
        lock_timeout_seconds: int = 300,
        retry_delay_seconds: int = 60,
    ) -> None:
        if min(
            batch_size,
            max_attempts,
            lock_timeout_seconds,
            retry_delay_seconds,
        ) <= 0:
            raise ValueError("Worker settings must be positive")

        self.session_factory = session_factory
        self.send_text = send_text
        self.batch_size = batch_size
        self.max_attempts = max_attempts
        self.lock_timeout = timedelta(seconds=lock_timeout_seconds)
        self.retry_delay_seconds = retry_delay_seconds

    async def claim_due_jobs(
        self,
        *,
        now: datetime | None = None,
    ) -> list[int]:
        now = now or datetime.now(timezone.utc)
        stale_before = now - self.lock_timeout

        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(NotificationJob)
                    .where(
                        NotificationJob.status == "processing",
                        or_(
                            NotificationJob.locked_at.is_(None),
                            NotificationJob.locked_at < stale_before,
                        ),
                    )
                    .values(status="pending", locked_at=None)
                )

                result = await session.scalars(
                    select(NotificationJob)
                    .where(
                        NotificationJob.status == "pending",
                        NotificationJob.scheduled_at <= now,
                    )
                    .order_by(
                        NotificationJob.scheduled_at,
                        NotificationJob.id,
                    )
                    .limit(self.batch_size)
                    .with_for_update(skip_locked=True)
                )
                jobs = list(result.all())
                for job in jobs:
                    job.status = "processing"
                    job.locked_at = now

                return [job.id for job in jobs]

    async def mark_sent(
        self,
        job_id: int,
        *,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(NotificationJob)
                    .where(
                        NotificationJob.id == job_id,
                        NotificationJob.status == "processing",
                    )
                    .values(
                        status="sent",
                        sent_at=now,
                        locked_at=None,
                        last_error=None,
                    )
                )

    async def mark_failed(
        self,
        job_id: int,
        error: Exception,
        *,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                job = await session.get(
                    NotificationJob,
                    job_id,
                    with_for_update=True,
                )
                if job is None or job.status != "processing":
                    return

                job.attempts += 1
                job.last_error = str(error)[:4000]
                job.locked_at = None
                if job.attempts >= self.max_attempts:
                    job.status = "failed"
                    return

                backoff = self.retry_delay_seconds * (
                    2 ** min(job.attempts - 1, 4)
                )
                job.status = "pending"
                job.scheduled_at = now + timedelta(seconds=backoff)

    async def process_job(self, job_id: int) -> None:
        try:
            async with self.session_factory() as session:
                job = await session.get(NotificationJob, job_id)
                if job is None or job.status != "processing":
                    return
                text = await render_notification(session, job)
                recipient_user_id = job.recipient_user_id

            await self.send_text(recipient_user_id, text)
        except Exception as exc:
            logger.exception("Notification job %s failed", job_id)
            await self.mark_failed(job_id, exc)
            return

        await self.mark_sent(job_id)
        logger.info("Notification job %s sent", job_id)

    async def run_once(self) -> int:
        job_ids = await self.claim_due_jobs()
        for job_id in job_ids:
            await self.process_job(job_id)
        return len(job_ids)


async def run() -> None:
    settings = get_settings()
    token = settings.max_bot_token.strip()
    if not token:
        raise RuntimeError("MAX_BOT_TOKEN is not configured")

    bot = MaxBot(token)
    worker = NotificationWorker(
        SessionLocal,
        bot.send_text,
        batch_size=settings.notification_batch_size,
        max_attempts=settings.notification_max_attempts,
        lock_timeout_seconds=settings.notification_lock_timeout_seconds,
        retry_delay_seconds=settings.notification_retry_delay_seconds,
    )

    logger.info("Notification worker started")
    try:
        while True:
            try:
                processed = await worker.run_once()
            except Exception:
                logger.exception("Notification worker iteration failed")
                processed = 0

            if processed == 0:
                await asyncio.sleep(
                    settings.notification_poll_interval_seconds
                )
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Notification worker stopped")
