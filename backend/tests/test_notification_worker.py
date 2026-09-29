import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import Field, NotificationJob, Participation, Slot
from app.notification_worker import NotificationWorker, slot_summary


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
