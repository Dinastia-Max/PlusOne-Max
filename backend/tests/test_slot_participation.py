import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.main import app
from app.models import Field, Participation, Slot
from app.routers.slots import join_slot, leave_slot, overlapping_slots_query


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class TransactionContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSession:
    def __init__(
        self,
        *results,
        overlapping_slot_id=None,
        participants_count=0,
    ):
        self.results = list(results)
        self.scalar_results = [None, overlapping_slot_id, participants_count]
        self.scalar_statements = []
        self.added = []
        self.deleted = []

    def begin(self):
        return TransactionContext()

    async def execute(self, statement):
        return FakeResult(self.results.pop(0))

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return self.scalar_results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)


def future_slot(**overrides):
    values = {
        "id": 1,
        "field_id": 1,
        "host_id": 10,
        "start_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "end_at": datetime.now(timezone.utc) + timedelta(hours=3),
        "min_players": 6,
        "max_players": 12,
        "has_ball": False,
    }
    values.update(overrides)
    return Slot(**values)


class JoinSlotTest(unittest.IsolatedAsyncioTestCase):
    async def test_user_can_join_available_slot(self):
        session = FakeSession(future_slot(), None, participants_count=5)

        response = await join_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(session.added), 1)
        self.assertEqual(session.added[0].slot_id, 1)
        self.assertEqual(session.added[0].user_id, 42)
        self.assertIn("pg_advisory_xact_lock", str(session.scalar_statements[0]))

    async def test_missing_slot_returns_not_found(self):
        session = FakeSession(None)

        with self.assertRaises(HTTPException) as context:
            await join_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)

    async def test_user_cannot_join_twice(self):
        participation = Participation(slot_id=1, user_id=42)
        session = FakeSession(future_slot(), participation)

        with self.assertRaises(HTTPException) as context:
            await join_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(context.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(context.exception.detail, "User has already joined this slot")

    async def test_user_cannot_join_overlapping_slot(self):
        session = FakeSession(
            future_slot(),
            None,
            overlapping_slot_id=2,
        )

        with self.assertRaises(HTTPException) as context:
            await join_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(context.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(context.exception.detail, "User has an overlapping slot")

    async def test_user_cannot_join_full_slot(self):
        slot = future_slot(max_players=12)
        session = FakeSession(slot, None, participants_count=12)

        with self.assertRaises(HTTPException) as context:
            await join_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(context.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(context.exception.detail, "Slot is full")

    async def test_user_cannot_join_past_slot(self):
        slot = future_slot(
            start_at=datetime.now(timezone.utc) - timedelta(hours=2),
            end_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        session = FakeSession(slot)

        with self.assertRaises(HTTPException) as context:
            await join_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(context.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(context.exception.detail, "Slot has already started")

    async def test_user_cannot_join_canceled_slot(self):
        slot = future_slot(canceled_at=datetime.now(timezone.utc))
        session = FakeSession(slot)

        with self.assertRaises(HTTPException) as context:
            await join_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(context.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(context.exception.detail, "Slot is canceled")


class LeaveSlotTest(unittest.IsolatedAsyncioTestCase):
    async def test_user_can_leave_slot(self):
        participation = Participation(slot_id=1, user_id=42)
        session = FakeSession(participation)

        response = await leave_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(session.deleted, [participation])

    async def test_missing_participation_returns_not_found(self):
        session = FakeSession(None)

        with self.assertRaises(HTTPException) as context:
            await leave_slot(slot_id=1, user_id=42, session=session)

        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)


class OverlappingSlotsQueryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_finds_hosted_and_joined_overlapping_slots(self):
        now = datetime.now(timezone.utc)
        target = future_slot(
            id=10,
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=4),
        )

        with Session(self.engine) as session:
            session.add(
                Field(
                    id=1,
                    name="Test field",
                    address="Test address",
                    district="SVAO",
                )
            )
            session.add_all(
                [
                    future_slot(
                        id=1,
                        host_id=43,
                        start_at=now + timedelta(hours=1),
                        end_at=now + timedelta(hours=3),
                    ),
                    future_slot(
                        id=2,
                        host_id=7,
                        start_at=now + timedelta(hours=3),
                        end_at=now + timedelta(hours=5),
                    ),
                ]
            )
            session.add(Participation(slot_id=2, user_id=42))
            session.commit()

            joined_result = session.scalars(
                overlapping_slots_query(42, target)
            ).all()
            hosted_result = session.scalars(
                overlapping_slots_query(43, target)
            ).all()

        self.assertEqual(joined_result, [2])
        self.assertEqual(hosted_result, [1])

    def test_allows_touching_boundaries_and_ignores_canceled_slots(self):
        now = datetime.now(timezone.utc)
        target = future_slot(
            id=10,
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=4),
        )

        with Session(self.engine) as session:
            session.add(
                Field(
                    id=1,
                    name="Test field",
                    address="Test address",
                    district="SVAO",
                )
            )
            session.add_all(
                [
                    future_slot(
                        id=1,
                        host_id=42,
                        start_at=now,
                        end_at=target.start_at,
                    ),
                    future_slot(
                        id=2,
                        host_id=42,
                        start_at=target.end_at,
                        end_at=now + timedelta(hours=6),
                    ),
                    future_slot(
                        id=3,
                        host_id=42,
                        start_at=now + timedelta(hours=3),
                        end_at=now + timedelta(hours=5),
                        canceled_at=now,
                    ),
                ]
            )
            session.commit()

            result = session.scalars(overlapping_slots_query(42, target)).all()

        self.assertEqual(result, [])


class CurrentUserHeaderTest(unittest.TestCase):
    def test_join_requires_user_header(self):
        response = TestClient(app).post("/slots/1/join")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_legacy_user_id_header_is_not_accepted(self):
        response = TestClient(app).post(
            "/slots/1/join",
            headers={"X-User-Id": "0"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
