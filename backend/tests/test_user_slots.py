import unittest
from datetime import datetime, timedelta, timezone

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.main import app
from app.models import Field, Participation, Slot
from app.routers.users import get_current_user_slots


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.rows)


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


def slot_row():
    now = datetime.now(timezone.utc)
    slot = Slot(
        id=1,
        field_id=1,
        host_id=42,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=3),
        min_players=6,
        max_players=12,
        has_ball=True,
    )
    field = Field(
        id=1,
        name="Stadium",
        address="1 Football Street",
        district="SVAO",
    )
    return slot, field, 7


class CurrentUserSlotsTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_user_slots_as_list_items(self):
        row = slot_row()
        session = FakeSession([row])

        result = await get_current_user_slots(user_id=42, session=session)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, row[0].id)
        self.assertEqual(result[0].participants_count, 7)
        self.assertEqual(result[0].field.id, row[1].id)

    async def test_empty_result_returns_empty_list(self):
        session = FakeSession([])

        result = await get_current_user_slots(user_id=42, session=session)

        self.assertEqual(result, [])

    async def test_selects_hosted_and_joined_active_slots(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        now = datetime.now(timezone.utc)

        with Session(engine) as session:
            session.add(
                Field(
                    id=1,
                    name="Stadium",
                    address="1 Football Street",
                    district="SVAO",
                )
            )
            session.add_all(
                [
                    Slot(
                        id=1,
                        field_id=1,
                        host_id=42,
                        start_at=now + timedelta(hours=1),
                        end_at=now + timedelta(hours=3),
                        min_players=6,
                        max_players=12,
                    ),
                    Slot(
                        id=2,
                        field_id=1,
                        host_id=7,
                        start_at=now + timedelta(hours=4),
                        end_at=now + timedelta(hours=6),
                        min_players=6,
                        max_players=12,
                    ),
                    Slot(
                        id=3,
                        field_id=1,
                        host_id=8,
                        start_at=now + timedelta(hours=7),
                        end_at=now + timedelta(hours=9),
                        min_players=6,
                        max_players=12,
                    ),
                    Slot(
                        id=4,
                        field_id=1,
                        host_id=42,
                        start_at=now + timedelta(hours=10),
                        end_at=now + timedelta(hours=12),
                        min_players=6,
                        max_players=12,
                        canceled_at=now,
                    ),
                ]
            )
            session.add_all(
                [
                    Participation(slot_id=1, user_id=42),
                    Participation(slot_id=1, user_id=7),
                    Participation(slot_id=2, user_id=42),
                    Participation(slot_id=2, user_id=8),
                ]
            )
            session.commit()

            result = await get_current_user_slots(
                user_id=42,
                session=AsyncSessionAdapter(session),
            )

        self.assertEqual([slot.id for slot in result], [1, 2])
        self.assertEqual(
            [slot.participants_count for slot in result],
            [2, 2],
        )


class CurrentUserSlotsHeaderTest(unittest.TestCase):
    def test_endpoint_requires_user_header(self):
        response = TestClient(app).get("/users/me/slots")

        self.assertEqual(
            response.status_code,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    def test_user_id_must_be_positive(self):
        response = TestClient(app).get(
            "/users/me/slots",
            headers={"X-User-Id": "0"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


if __name__ == "__main__":
    unittest.main()
