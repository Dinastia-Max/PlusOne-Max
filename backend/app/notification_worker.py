import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, or_, select, update
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot import MaxBot
from app.config import get_settings
from app.database import SessionLocal
from app.models import Field, NotificationJob, Participation, Slot


MOSCOW_TZ = ZoneInfo("Europe/Moscow")
SendText = Callable[[int, str], Awaitable[None]]

JOB_STATUSES = ("pending", "processing", "sent", "failed", "canceled")
SEND_TIMEOUT_SECONDS = 30
SCHEMA_CHECK_INTERVAL_SECONDS = 5
BACKLOG_WARNING_SECONDS = 300
LOCK_EXPIRED_ERROR = "Processing lock expired: worker stopped before finishing"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("plusone.notification_worker")


class NotificationRenderError(ValueError):
    pass


def describe_error(error: Exception) -> str:
    message = f"{type(error).__name__}: {error}"
    if isinstance(error, httpx.HTTPStatusError):
        body = error.response.text.strip()
        if body:
            message += f" | response: {body[:500]}"
    return message[:4000]


def retry_backoff_seconds(attempts: int, base_delay_seconds: int) -> int:
    """Delay before the next attempt: base, 2x, 4x, 8x, then 16x at most."""
    return base_delay_seconds * (2 ** min(max(attempts, 1) - 1, 4))


@dataclass(frozen=True)
class QueueStats:
    counts: dict[str, int]
    due_pending: int
    oldest_due_lag_seconds: float | None

    def format(self) -> str:
        counts = " ".join(
            f"{status}={self.counts.get(status, 0)}" for status in JOB_STATUSES
        )
        lag = (
            f"{self.oldest_due_lag_seconds:.0f}s"
            if self.oldest_due_lag_seconds is not None
            else "0s"
        )
        return f"{counts} due={self.due_pending} oldest_due_lag={lag}"


async def collect_stats(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
) -> QueueStats:
    now = now or datetime.now(timezone.utc)
    async with session_factory() as session:
        rows = await session.execute(
            select(NotificationJob.status, func.count()).group_by(
                NotificationJob.status
            )
        )
        counts = {status: 0 for status in JOB_STATUSES}
        counts.update({status: total for status, total in rows.all()})

        due = await session.execute(
            select(func.count(), func.min(NotificationJob.scheduled_at)).where(
                NotificationJob.status == "pending",
                NotificationJob.scheduled_at <= now,
            )
        )
        due_count, oldest_due = due.one()

    lag = None
    if oldest_due is not None:
        if oldest_due.tzinfo is None:
            oldest_due = oldest_due.replace(tzinfo=timezone.utc)
        lag = max((now - oldest_due).total_seconds(), 0.0)
    return QueueStats(counts=counts, due_pending=due_count, oldest_due_lag_seconds=lag)


def alembic_head_revisions() -> set[str]:
    backend_dir = Path(__file__).resolve().parent.parent
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    return set(ScriptDirectory.from_config(config).get_heads())


async def database_revision(
    session_factory: async_sessionmaker[AsyncSession],
) -> set[str]:
    async with session_factory() as session:
        result = await session.execute(sql_text("SELECT version_num FROM alembic_version"))
        return {row[0] for row in result.all()}


async def wait_for_migrations(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stop: asyncio.Event | None = None,
    interval_seconds: float = SCHEMA_CHECK_INTERVAL_SECONDS,
) -> bool:
    """Blocks until the API has applied all Alembic migrations.

    The API container runs `alembic upgrade head` on start. The worker never
    migrates the database itself, so two services cannot race on DDL.
    """
    expected = alembic_head_revisions()
    while stop is None or not stop.is_set():
        try:
            current = await database_revision(session_factory)
        except Exception as exc:
            logger.warning(
                "Database schema is not ready yet (%s); retrying in %ss",
                type(exc).__name__,
                interval_seconds,
            )
        else:
            if current == expected:
                logger.info("Database schema is up to date: %s", ", ".join(sorted(current)))
                return True
            logger.warning(
                "Waiting for migrations: database=%s expected=%s",
                ", ".join(sorted(current)) or "none",
                ", ".join(sorted(expected)),
            )

        if stop is None:
            await asyncio.sleep(interval_seconds)
        else:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass
    return False


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

    async def recover_stale_jobs(
        self,
        session: AsyncSession,
        stale_before: datetime,
    ) -> None:
        """Returns jobs abandoned in `processing` to the queue.

        A lost lock counts as an attempt, so a job that keeps killing the
        worker ends up as `failed` instead of looping forever.
        """
        is_stale = (
            NotificationJob.status == "processing",
            or_(
                NotificationJob.locked_at.is_(None),
                NotificationJob.locked_at < stale_before,
            ),
        )
        exhausted = await session.scalars(
            update(NotificationJob)
            .where(*is_stale, NotificationJob.attempts + 1 >= self.max_attempts)
            .values(
                status="failed",
                attempts=NotificationJob.attempts + 1,
                locked_at=None,
                last_error=LOCK_EXPIRED_ERROR,
            )
            .returning(NotificationJob.id)
        )
        for job_id in exhausted.all():
            logger.error(
                "Notification job %s failed permanently: %s",
                job_id,
                LOCK_EXPIRED_ERROR,
            )

        recovered = await session.scalars(
            update(NotificationJob)
            .where(*is_stale)
            .values(
                status="pending",
                attempts=NotificationJob.attempts + 1,
                locked_at=None,
                last_error=LOCK_EXPIRED_ERROR,
            )
            .returning(NotificationJob.id)
        )
        for job_id in recovered.all():
            logger.warning(
                "Notification job %s was stuck in processing; returned to queue",
                job_id,
            )

    async def claim_due_job(
        self,
        *,
        now: datetime | None = None,
    ) -> int | None:
        now = now or datetime.now(timezone.utc)
        stale_before = now - self.lock_timeout

        async with self.session_factory() as session:
            async with session.begin():
                await self.recover_stale_jobs(session, stale_before)

                job = await session.scalar(
                    select(NotificationJob)
                    .where(
                        NotificationJob.status == "pending",
                        NotificationJob.scheduled_at <= now,
                    )
                    .order_by(
                        NotificationJob.scheduled_at,
                        NotificationJob.id,
                    )
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                if job is None:
                    return None

                job.status = "processing"
                job.locked_at = now
                return job.id

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
                job.last_error = describe_error(error)
                job.locked_at = None
                if job.attempts >= self.max_attempts:
                    job.status = "failed"
                    logger.error(
                        "Notification job %s (%s, user %s) failed permanently "
                        "after %s attempts: %s",
                        job.id,
                        job.notification_type,
                        job.recipient_user_id,
                        job.attempts,
                        job.last_error,
                    )
                    return

                backoff = retry_backoff_seconds(
                    job.attempts,
                    self.retry_delay_seconds,
                )
                job.status = "pending"
                job.scheduled_at = now + timedelta(seconds=backoff)
                logger.warning(
                    "Notification job %s (%s, user %s) attempt %s/%s failed: "
                    "%s; retry in %ss",
                    job.id,
                    job.notification_type,
                    job.recipient_user_id,
                    job.attempts,
                    self.max_attempts,
                    job.last_error,
                    backoff,
                )

    async def process_job(self, job_id: int) -> None:
        try:
            async with self.session_factory() as session:
                job = await session.get(NotificationJob, job_id)
                if job is None or job.status != "processing":
                    return
                text = await render_notification(session, job)
                recipient_user_id = job.recipient_user_id

            await asyncio.wait_for(
                self.send_text(recipient_user_id, text),
                timeout=SEND_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            if not isinstance(exc, (httpx.HTTPError, asyncio.TimeoutError)):
                logger.exception("Notification job %s crashed", job_id)
            await self.mark_failed(job_id, exc)
            return

        await self.mark_sent(job_id)
        logger.info("Notification job %s sent", job_id)

    async def run_once(self, stop: asyncio.Event | None = None) -> int:
        processed = 0
        for _ in range(self.batch_size):
            if stop is not None and stop.is_set():
                break

            job_id = await self.claim_due_job()
            if job_id is None:
                break

            await self.process_job(job_id)
            processed += 1
        return processed


def install_stop_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass


async def sleep_or_stop(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


async def log_queue_stats(session_factory: async_sessionmaker[AsyncSession]) -> None:
    try:
        stats = await collect_stats(session_factory)
    except Exception:
        logger.exception("Failed to collect notification queue stats")
        return

    message = f"Notification queue: {stats.format()}"
    lag = stats.oldest_due_lag_seconds
    if lag is not None and lag > BACKLOG_WARNING_SECONDS:
        logger.warning("%s (delivery is lagging)", message)
    else:
        logger.info(message)


async def run() -> None:
    settings = get_settings()
    token = settings.max_bot_token.strip()
    if not token:
        raise RuntimeError("MAX_BOT_TOKEN is not configured")

    stop = asyncio.Event()
    install_stop_handlers(stop)

    bot = MaxBot(token)
    worker = NotificationWorker(
        SessionLocal,
        bot.send_text,
        batch_size=settings.notification_batch_size,
        max_attempts=settings.notification_max_attempts,
        lock_timeout_seconds=settings.notification_lock_timeout_seconds,
        retry_delay_seconds=settings.notification_retry_delay_seconds,
    )

    try:
        if not await wait_for_migrations(SessionLocal, stop=stop):
            return

        logger.info(
            "Notification worker started: poll=%ss batch=%s max_attempts=%s "
            "lock_timeout=%ss retry_delay=%ss",
            settings.notification_poll_interval_seconds,
            settings.notification_batch_size,
            settings.notification_max_attempts,
            settings.notification_lock_timeout_seconds,
            settings.notification_retry_delay_seconds,
        )
        loop = asyncio.get_running_loop()
        next_stats_at = loop.time()
        while not stop.is_set():
            if loop.time() >= next_stats_at:
                await log_queue_stats(SessionLocal)
                next_stats_at = (
                    loop.time() + settings.notification_stats_interval_seconds
                )

            try:
                processed = await worker.run_once(stop)
            except Exception:
                logger.exception("Notification worker iteration failed")
                processed = 0

            if processed == 0:
                await sleep_or_stop(
                    stop,
                    settings.notification_poll_interval_seconds,
                )
    finally:
        await bot.close()
        logger.info("Notification worker stopped")


if __name__ == "__main__":
    asyncio.run(run())
