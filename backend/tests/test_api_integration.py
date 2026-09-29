import asyncio
import hashlib
import hmac
import json
import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import get_db
from app.main import app
from app.models import Field, NotificationJob, Participation, Slot


RUN_INTEGRATION_TESTS = os.getenv("RUN_API_INTEGRATION_TESTS") == "1"
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "")
TEST_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "test-bot-token")


@unittest.skipUnless(
    RUN_INTEGRATION_TESTS,
    "Set RUN_API_INTEGRATION_TESTS=1 to run PostgreSQL integration tests",
)
class ApiIntegrationTest(unittest.IsolatedAsyncioTestCase):
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
                session.add(
                    Field(
                        id=1,
                        name="Тестовое поле",
                        address="Москва, Тестовая улица, 1",
                        district="SVAO",
                    )
                )

        async def override_get_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.client.aclose()
        await self.engine.dispose()

    @staticmethod
    def headers(user_id: int) -> dict[str, str]:
        params = {
            "auth_date": str(int(time.time())),
            "query_id": f"integration-test-{user_id}",
            "user": json.dumps(
                {"id": user_id, "first_name": "Test"},
                separators=(",", ":"),
            ),
        }
        launch_params = "\n".join(
            f"{key}={value}" for key, value in sorted(params.items())
        )
        secret_key = hmac.new(
            b"WebAppData",
            TEST_BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()
        params["hash"] = hmac.new(
            secret_key,
            launch_params.encode(),
            hashlib.sha256,
        ).hexdigest()
        init_data = "&".join(
            f"{key}={quote(value, safe='')}" for key, value in params.items()
        )
        return {"X-Max-Init-Data": init_data}

    @staticmethod
    def slot_payload(
        *,
        start_at: datetime | None = None,
        max_players: int = 10,
    ) -> dict:
        start_at = start_at or datetime.now(timezone.utc) + timedelta(days=1)
        return {
            "field_id": 1,
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(hours=2)).isoformat(),
            "min_players": 1,
            "max_players": max_players,
            "has_ball": True,
        }

    async def create_slot(
        self,
        *,
        host_id: int = 101,
        max_players: int = 10,
        start_at: datetime | None = None,
    ) -> int:
        response = await self.client.post(
            "/slots",
            headers=self.headers(host_id),
            json=self.slot_payload(
                max_players=max_players,
                start_at=start_at,
            ),
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    async def test_complete_user_flow(self):
        slot_id = await self.create_slot(host_id=101)

        slots_response = await self.client.get("/slots")
        self.assertEqual(slots_response.status_code, 200)
        self.assertEqual([item["id"] for item in slots_response.json()], [slot_id])

        detail_response = await self.client.get(f"/slots/{slot_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["host_id"], 101)

        join_response = await self.client.post(
            f"/slots/{slot_id}/join",
            headers=self.headers(202),
        )
        self.assertEqual(join_response.status_code, 204)

        games_response = await self.client.get(
            "/users/me/slots",
            headers=self.headers(202),
        )
        self.assertEqual(games_response.status_code, 200)
        self.assertEqual(games_response.json()[0]["id"], slot_id)
        self.assertEqual(games_response.json()[0]["role"], "participant")

        leave_response = await self.client.delete(
            f"/slots/{slot_id}/join",
            headers=self.headers(202),
        )
        self.assertEqual(leave_response.status_code, 204)

        cancel_response = await self.client.delete(
            f"/slots/{slot_id}",
            headers=self.headers(101),
        )
        self.assertEqual(cancel_response.status_code, 204)

        hidden_response = await self.client.get(f"/slots/{slot_id}")
        self.assertEqual(hidden_response.status_code, 404)

    async def test_api_errors(self):
        unauthorized = await self.client.post(
            "/slots",
            json=self.slot_payload(),
        )
        self.assertEqual(unauthorized.status_code, 401)

        missing = await self.client.post(
            "/slots/999/join",
            headers=self.headers(202),
        )
        self.assertEqual(missing.status_code, 404)

        slot_id = await self.create_slot(max_players=1)
        first_join = await self.client.post(
            f"/slots/{slot_id}/join",
            headers=self.headers(202),
        )
        self.assertEqual(first_join.status_code, 204)

        repeated_join = await self.client.post(
            f"/slots/{slot_id}/join",
            headers=self.headers(202),
        )
        self.assertEqual(repeated_join.status_code, 409)

        full_slot = await self.client.post(
            f"/slots/{slot_id}/join",
            headers=self.headers(303),
        )
        self.assertEqual(full_slot.status_code, 409)
        self.assertEqual(full_slot.json()["detail"], "Slot is full")

        async with self.session_factory() as session:
            async with session.begin():
                started_slot = Slot(
                    field_id=1,
                    host_id=101,
                    start_at=datetime.now(timezone.utc) - timedelta(hours=2),
                    end_at=datetime.now(timezone.utc) - timedelta(hours=1),
                    min_players=1,
                    max_players=10,
                )
                session.add(started_slot)
                await session.flush()
                started_slot_id = started_slot.id

        started = await self.client.post(
            f"/slots/{started_slot_id}/join",
            headers=self.headers(404),
        )
        self.assertEqual(started.status_code, 409)
        self.assertEqual(started.json()["detail"], "Slot has already started")

        canceled_slot_id = await self.create_slot(host_id=505)
        await self.client.delete(
            f"/slots/{canceled_slot_id}",
            headers=self.headers(505),
        )
        canceled = await self.client.post(
            f"/slots/{canceled_slot_id}/join",
            headers=self.headers(606),
        )
        self.assertEqual(canceled.status_code, 409)
        self.assertEqual(canceled.json()["detail"], "Slot is canceled")

    async def test_host_contact_is_private(self):
        create_response = await self.client.post(
            "/slots",
            headers=self.headers(101),
            json={
                **self.slot_payload(),
                "host_contact_type": "phone",
                "host_phone": "+7 (999) 123-45-67",
            },
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        slot_id = create_response.json()["id"]
        self.assertNotIn("host_contact", create_response.json())

        public_list = await self.client.get("/slots")
        public_detail = await self.client.get(f"/slots/{slot_id}")
        self.assertNotIn("host_contact", public_list.json()[0])
        self.assertNotIn("host_contact", public_detail.json())

        unauthorized = await self.client.get(f"/slots/{slot_id}/host-contact")
        self.assertEqual(unauthorized.status_code, 401)

        outsider = await self.client.get(
            f"/slots/{slot_id}/host-contact",
            headers=self.headers(303),
        )
        self.assertEqual(outsider.status_code, 403)

        host_contact = await self.client.get(
            f"/slots/{slot_id}/host-contact",
            headers=self.headers(101),
        )
        self.assertEqual(host_contact.status_code, 200)
        self.assertEqual(
            host_contact.json(),
            {
                "type": "phone",
                "label": "+79991234567",
                "href": "tel:+79991234567",
            },
        )

        join_response = await self.client.post(
            f"/slots/{slot_id}/join",
            headers=self.headers(202),
        )
        self.assertEqual(join_response.status_code, 204)
        participant_contact = await self.client.get(
            f"/slots/{slot_id}/host-contact",
            headers=self.headers(202),
        )
        self.assertEqual(participant_contact.status_code, 200)
        self.assertEqual(participant_contact.json(), host_contact.json())

        await self.client.delete(
            f"/slots/{slot_id}/join",
            headers=self.headers(202),
        )
        former_participant = await self.client.get(
            f"/slots/{slot_id}/host-contact",
            headers=self.headers(202),
        )
        self.assertEqual(former_participant.status_code, 403)

    async def test_only_one_user_gets_last_place(self):
        slot_id = await self.create_slot(max_players=1)

        responses = await asyncio.gather(
            self.client.post(
                f"/slots/{slot_id}/join",
                headers=self.headers(202),
            ),
            self.client.post(
                f"/slots/{slot_id}/join",
                headers=self.headers(303),
            ),
        )

        self.assertEqual(sorted(response.status_code for response in responses), [204, 409])

        participants = await self.client.get(f"/slots/{slot_id}/participants")
        self.assertEqual(participants.status_code, 200)
        self.assertEqual(len(participants.json()), 1)

    async def test_notification_jobs_follow_slot_lifecycle(self):
        slot_id = await self.create_slot(
            host_id=101,
            start_at=datetime.now(timezone.utc) + timedelta(days=2),
        )

        async with self.session_factory() as session:
            host_jobs = (
                await session.scalars(
                    select(NotificationJob).where(
                        NotificationJob.slot_id == slot_id,
                        NotificationJob.recipient_user_id == 101,
                    )
                )
            ).all()
        self.assertEqual(
            {job.notification_type for job in host_jobs},
            {"reminder_24h", "reminder_2h", "game_status_1h"},
        )

        joined = await self.client.post(
            f"/slots/{slot_id}/join",
            headers=self.headers(202),
        )
        self.assertEqual(joined.status_code, 204)

        async with self.session_factory() as session:
            participant_jobs = (
                await session.scalars(
                    select(NotificationJob).where(
                        NotificationJob.slot_id == slot_id,
                        NotificationJob.recipient_user_id == 202,
                    )
                )
            ).all()
        self.assertEqual(
            {job.notification_type for job in participant_jobs},
            {
                "joined",
                "reminder_24h",
                "reminder_2h",
                "game_status_1h",
            },
        )

        left = await self.client.delete(
            f"/slots/{slot_id}/join",
            headers=self.headers(202),
        )
        self.assertEqual(left.status_code, 204)

        joined_again = await self.client.post(
            f"/slots/{slot_id}/join",
            headers=self.headers(303),
        )
        self.assertEqual(joined_again.status_code, 204)
        canceled = await self.client.delete(
            f"/slots/{slot_id}",
            headers=self.headers(101),
        )
        self.assertEqual(canceled.status_code, 204)

        async with self.session_factory() as session:
            user_202_jobs = (
                await session.scalars(
                    select(NotificationJob).where(
                        NotificationJob.slot_id == slot_id,
                        NotificationJob.recipient_user_id == 202,
                    )
                )
            ).all()
            cancellation_jobs = (
                await session.scalars(
                    select(NotificationJob).where(
                        NotificationJob.slot_id == slot_id,
                        NotificationJob.recipient_user_id == 303,
                        NotificationJob.notification_type == "slot_canceled",
                    )
                )
            ).all()
            participant_left_jobs = (
                await session.scalars(
                    select(NotificationJob).where(
                        NotificationJob.slot_id == slot_id,
                        NotificationJob.recipient_user_id == 101,
                        NotificationJob.notification_type
                        == "participant_left",
                    )
                )
            ).all()

        self.assertTrue(user_202_jobs)
        self.assertTrue(
            all(job.status == "canceled" for job in user_202_jobs)
        )
        self.assertEqual(len(cancellation_jobs), 1)
        self.assertEqual(cancellation_jobs[0].status, "pending")
        self.assertEqual(len(participant_left_jobs), 1)


if __name__ == "__main__":
    unittest.main()
