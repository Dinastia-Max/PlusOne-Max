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
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import get_db
from app.main import app
from app.models import Field, Participation, Slot


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
        host_participates: bool = True,
    ) -> dict:
        start_at = start_at or datetime.now(timezone.utc) + timedelta(days=1)
        return {
            "field_id": 1,
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(hours=2)).isoformat(),
            "min_players": 1,
            "max_players": max_players,
            "has_ball": True,
            "host_participates": host_participates,
        }

    async def create_slot(
        self,
        *,
        host_id: int = 101,
        max_players: int = 10,
        host_participates: bool = True,
    ) -> int:
        response = await self.client.post(
            "/slots",
            headers=self.headers(host_id),
            json=self.slot_payload(
                max_players=max_players,
                host_participates=host_participates,
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

    async def test_host_participation_choice(self):
        participating_response = await self.client.post(
            "/slots",
            headers=self.headers(101),
            json=self.slot_payload(host_participates=True),
        )
        self.assertEqual(participating_response.status_code, 201)
        participating_slot = participating_response.json()
        self.assertEqual(participating_slot["participants_count"], 1)

        participants = await self.client.get(
            f"/slots/{participating_slot['id']}/participants"
        )
        self.assertEqual(participants.status_code, 200)
        self.assertEqual(
            [participant["user_id"] for participant in participants.json()],
            [101],
        )

        duplicate = await self.client.post(
            f"/slots/{participating_slot['id']}/join",
            headers=self.headers(101),
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(
            duplicate.json()["detail"],
            "User has already joined this slot",
        )

        my_games = await self.client.get(
            "/users/me/slots",
            headers=self.headers(101),
        )
        self.assertEqual(my_games.status_code, 200)
        participating_game = next(
            game for game in my_games.json()
            if game["id"] == participating_slot["id"]
        )
        self.assertEqual(participating_game["role"], "host")
        self.assertEqual(participating_game["participants_count"], 1)

        organizing_response = await self.client.post(
            "/slots",
            headers=self.headers(202),
            json=self.slot_payload(host_participates=False),
        )
        self.assertEqual(organizing_response.status_code, 201)
        organizing_slot = organizing_response.json()
        self.assertEqual(organizing_slot["participants_count"], 0)

        participants = await self.client.get(
            f"/slots/{organizing_slot['id']}/participants"
        )
        self.assertEqual(participants.status_code, 200)
        self.assertEqual(participants.json(), [])

    async def test_participating_host_cannot_create_overlapping_slot(self):
        start_at = datetime.now(timezone.utc) + timedelta(days=2)
        first = await self.client.post(
            "/slots",
            headers=self.headers(101),
            json=self.slot_payload(
                start_at=start_at,
                host_participates=True,
            ),
        )
        self.assertEqual(first.status_code, 201, first.text)

        overlapping = await self.client.post(
            "/slots",
            headers=self.headers(101),
            json=self.slot_payload(
                start_at=start_at + timedelta(minutes=30),
                host_participates=True,
            ),
        )
        self.assertEqual(overlapping.status_code, 409)
        self.assertEqual(
            overlapping.json()["detail"],
            "User has an overlapping slot",
        )

        organizing_only = await self.client.post(
            "/slots",
            headers=self.headers(101),
            json=self.slot_payload(
                start_at=start_at + timedelta(minutes=30),
                host_participates=False,
            ),
        )
        self.assertEqual(organizing_only.status_code, 201, organizing_only.text)

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

        slot_id = await self.create_slot(
            max_players=1,
            host_participates=False,
        )
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

    async def test_only_one_user_gets_last_place(self):
        slot_id = await self.create_slot(
            max_players=1,
            host_participates=False,
        )

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


if __name__ == "__main__":
    unittest.main()
