import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import Field, NotificationJob, Participation, Slot
from app.notification_worker import (
    LOCK_EXPIRED_ERROR,
    NotificationWorker,
    QueueStats,
    alembic_head_revisions,
    collect_stats,
    describe_error,
    retry_backoff_seconds,
    slot_summary,
    wait_for_migrations,
)


RUN_INTEGRATION_TESTS = os.getenv("RUN_API_INTEGRATION_TESTS") == "1"
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "")


class NotificationFormattingTest(unittest.TestCase):
    def test_formats_slot_time_in_moscow_timezone(self):
        slot = Slot(
            start_at=datetime(2026, 1, 15, 15, 30, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 15, 17, 0, tzinfo=timezone.utc),
        )
        field = Field(
            name="Тестовое поле",
            address="Москва, Тестовая улица, 1",
        )

        summary = slot_summary(slot, field)

        self.assertEqual(
            summary,
            "15.01.2026, 18:30–20:00\n"
            "Тестовое поле, Москва, Тестовая улица, 1",
        )


class RetryBackoffTest(unittest.TestCase):
    def test_delay_doubles_and_is_capped(self):
        delays = [retry_backoff_seconds(attempt, 60) for attempt in range(1, 8)]

        self.assertEqual(delays, [60, 120, 240, 480, 960, 960, 960])


class DescribeErrorTest(unittest.TestCase):
    def test_includes_max_response_body(self):
        request = httpx.Request("POST", "https://platform-api2.max.ru/messages")
        response = httpx.Response(
            403,
            request=request,
            text='{"code":"chat.denied"}',
        )
        error = httpx.HTTPStatusError(
            "Forbidden",
            request=request,
            response=response,
        )

        message = describe_error(error)

        self.assertIn("HTTPStatusError", message)
        self.assertIn("chat.denied", message)

    def test_plain_error(self):
        self.assertEqual(
            describe_error(RuntimeError("MAX is unavailable")),
            "RuntimeError: MAX is unavailable",
        )


class QueueStatsTest(unittest.TestCase):
    def test_format_lists_every_status(self):
        stats = QueueStats(
            counts={"pending": 2, "sent": 5},
            due_pending=1,
            oldest_due_lag_seconds=12.4,
        )

        self.assertEqual(
            stats.format(),
            "pending=2 processing=0 sent=5 failed=0 canceled=0 "
            "due=1 oldest_due_lag=12s",
        )


class WaitForMigrationsTest(unittest.IsolatedAsyncioTestCase):
    async def test_waits_until_database_reaches_head(self):
        head = next(iter(alembic_head_revisions()))
        revisions = [OSError("no database"), {"old"}, {head}]

        async def fake_revision(_session_factory):
            value = revisions.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        with patch(
            "app.notification_worker.database_revision",
            side_effect=fake_revision,
        ):
            ready = await wait_for_migrations(None, interval_seconds=0)

        self.assertTrue(ready)
        self.assertEqual(revisions, [])

    async def test_stops_waiting_when_asked(self):
        stop = asyncio.Event()
        stop.set()

        ready = await wait_for_migrations(None, stop=stop, interval_seconds=0)

        self.assertFalse(ready)


@unittest.skipUnless(
    RUN_INTEGRATION_TESTS,
    "Set RUN_API_INTEGRATION_TESTS=1 to run PostgreSQL integration tests",
)
class NotificationWorkerIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            TEST_DATABASE_URL,
            poolclass=NullPool,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(delete(NotificationJob))
                await session.execute(delete(Participation))
                await session.execute(delete(Slot))
                await session.execute(delete(Field))
                field = Field(
                    name="Тестовое поле",
                    address="Москва, Тестовая улица, 1",
                    district="SVAO",
                )
                session.add(field)
                await session.flush()

                self.slot = Slot(
                    field_id=field.id,
                    host_id=101,
                    start_at=datetime.now(timezone.utc) + timedelta(days=1),
                    end_at=datetime.now(timezone.utc)
                    + timedelta(days=1, hours=2),
                    min_players=2,
                    max_players=10,
                )
                session.add(self.slot)
                await session.flush()
                self.slot_id = self.slot.id

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def add_job(
        self,
        *,
        notification_type: str = "reminder_2h",
        status: str = "pending",
        scheduled_at: datetime | None = None,
        locked_at: datetime | None = None,
    ) -> int:
        scheduled_at = scheduled_at or (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        async with self.session_factory() as session:
            async with session.begin():
                job = NotificationJob(
                    slot_id=self.slot_id,
                    recipient_user_id=202,
                    notification_type=notification_type,
                    scheduled_at=scheduled_at,
                    status=status,
                    locked_at=locked_at,
                )
                session.add(job)
                await session.flush()
                return job.id

    async def get_job(self, job_id: int) -> NotificationJob:
        async with self.session_factory() as session:
            result = await session.execute(
                select(NotificationJob).where(NotificationJob.id == job_id)
            )
            return result.scalar_one()

    async def test_sends_due_job_and_marks_it_sent(self):
        job_id = await self.add_job()
        messages: list[tuple[int, str]] = []

        async def send_text(user_id: int, text: str) -> None:
            messages.append((user_id, text))

        worker = NotificationWorker(self.session_factory, send_text)

        processed = await worker.run_once()

        job = await self.get_job(job_id)
        self.assertEqual(processed, 1)
        self.assertEqual(job.status, "sent")
        self.assertIsNotNone(job.sent_at)
        self.assertIsNone(job.locked_at)
        self.assertEqual(messages[0][0], 202)
        self.assertIn("игра через 2 часа", messages[0][1])

    async def test_retries_then_marks_repeated_failure_as_failed(self):
        job_id = await self.add_job()

        async def send_text(user_id: int, text: str) -> None:
            raise RuntimeError("MAX is unavailable")

        worker = NotificationWorker(
            self.session_factory,
            send_text,
            max_attempts=2,
            retry_delay_seconds=1,
        )

        await worker.run_once()
        first_attempt = await self.get_job(job_id)
        self.assertEqual(first_attempt.status, "pending")
        self.assertEqual(first_attempt.attempts, 1)
        self.assertIn("MAX is unavailable", first_attempt.last_error)

        async with self.session_factory() as session:
            async with session.begin():
                job = await session.get(NotificationJob, job_id)
                job.scheduled_at = datetime.now(timezone.utc) - timedelta(
                    seconds=1
                )

        await worker.run_once()
        second_attempt = await self.get_job(job_id)
        self.assertEqual(second_attempt.status, "failed")
        self.assertEqual(second_attempt.attempts, 2)

    async def test_recovers_stale_processing_job(self):
        job_id = await self.add_job(
            status="processing",
            locked_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        messages: list[str] = []

        async def send_text(user_id: int, text: str) -> None:
            messages.append(text)

        worker = NotificationWorker(
            self.session_factory,
            send_text,
            lock_timeout_seconds=60,
        )

        processed = await worker.run_once()

        job = await self.get_job(job_id)
        self.assertEqual(processed, 1)
        self.assertEqual(job.status, "sent")
        self.assertEqual(len(messages), 1)
        self.assertEqual(job.attempts, 1)

    async def test_stale_processing_job_fails_after_last_attempt(self):
        job_id = await self.add_job(
            status="processing",
            locked_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        async with self.session_factory() as session:
            async with session.begin():
                job = await session.get(NotificationJob, job_id)
                job.attempts = 4
        send_text = AsyncMock()
        worker = NotificationWorker(
            self.session_factory,
            send_text,
            max_attempts=5,
            lock_timeout_seconds=60,
        )

        processed = await worker.run_once()

        job = await self.get_job(job_id)
        self.assertEqual(processed, 0)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.attempts, 5)
        self.assertEqual(job.last_error, LOCK_EXPIRED_ERROR)
        send_text.assert_not_awaited()

    async def test_fresh_processing_job_is_left_alone(self):
        job_id = await self.add_job(
            status="processing",
            locked_at=datetime.now(timezone.utc),
        )
        send_text = AsyncMock()
        worker = NotificationWorker(
            self.session_factory,
            send_text,
            lock_timeout_seconds=300,
        )

        processed = await worker.run_once()

        job = await self.get_job(job_id)
        self.assertEqual(processed, 0)
        self.assertEqual(job.status, "processing")

    async def test_stop_returns_unsent_jobs_to_queue(self):
        first_id = await self.add_job()
        second_id = await self.add_job()
        stop = asyncio.Event()
        messages: list[str] = []

        async def send_text(user_id: int, text: str) -> None:
            messages.append(text)
            stop.set()

        worker = NotificationWorker(self.session_factory, send_text)

        await worker.run_once(stop)

        first = await self.get_job(first_id)
        second = await self.get_job(second_id)
        self.assertEqual(len(messages), 1)
        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "pending")
        self.assertEqual(second.attempts, 0)

    async def test_two_workers_do_not_preclaim_each_others_jobs(self):
        first_id = await self.add_job()
        second_id = await self.add_job()
        first_send_started = asyncio.Event()
        finish_first_send = asyncio.Event()
        sent_job_ids: list[int] = []

        async def slow_send(user_id: int, text: str) -> None:
            first_send_started.set()
            await finish_first_send.wait()
            sent_job_ids.append(first_id)

        async def fast_send(user_id: int, text: str) -> None:
            sent_job_ids.append(second_id)

        first_worker = NotificationWorker(
            self.session_factory,
            slow_send,
            batch_size=2,
        )
        second_worker = NotificationWorker(
            self.session_factory,
            fast_send,
            batch_size=2,
        )

        first_run = asyncio.create_task(first_worker.run_once())
        await asyncio.wait_for(first_send_started.wait(), timeout=1)

        second_before = await self.get_job(second_id)
        self.assertEqual(second_before.status, "pending")
        self.assertIsNone(second_before.locked_at)

        second_processed = await second_worker.run_once()
        finish_first_send.set()
        first_processed = await asyncio.wait_for(first_run, timeout=1)

        first = await self.get_job(first_id)
        second = await self.get_job(second_id)
        self.assertEqual(first_processed, 1)
        self.assertEqual(second_processed, 1)
        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "sent")
        self.assertCountEqual(sent_job_ids, [first_id, second_id])

    async def test_collects_queue_stats(self):
        await self.add_job(status="sent")
        await self.add_job(status="failed")
        await self.add_job(
            scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=90)
        )
        await self.add_job(
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        stats = await collect_stats(self.session_factory)

        self.assertEqual(stats.counts["sent"], 1)
        self.assertEqual(stats.counts["failed"], 1)
        self.assertEqual(stats.counts["pending"], 2)
        self.assertEqual(stats.due_pending, 1)
        self.assertGreaterEqual(stats.oldest_due_lag_seconds, 89)

    async def test_ignores_future_job(self):
        job_id = await self.add_job(
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        send_text = AsyncMock()
        worker = NotificationWorker(self.session_factory, send_text)

        processed = await worker.run_once()

        job = await self.get_job(job_id)
        self.assertEqual(processed, 0)
        self.assertEqual(job.status, "pending")
        send_text.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
