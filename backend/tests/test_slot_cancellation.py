import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from app.models import Slot
from app.routers.slots import cancel_slot
from test_support import ConfiguredAuthTestCase


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
    def __init__(self, slot):
        self.slot = slot

    def begin(self):
        return TransactionContext()

    async def execute(self, statement):
        return FakeResult(self.slot)


def future_slot(**overrides) -> Slot:
    values = {
        "id": 1,
        "field_id": 1,
        "host_id": 42,
        "start_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "end_at": datetime.now(timezone.utc) + timedelta(hours=3),
        "min_players": 6,
        "max_players": 12,
        "has_ball": False,
    }
    values.update(overrides)
    return Slot(**values)


class CancelSlotTest(unittest.IsolatedAsyncioTestCase):
    async def test_host_can_cancel_slot(self):
        slot = future_slot()
        before = datetime.now(timezone.utc)

        response = await cancel_slot(
            slot_id=slot.id,
            user_id=slot.host_id,
            session=FakeSession(slot),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNotNone(slot.canceled_at)
        self.assertGreaterEqual(slot.canceled_at, before)
        self.assertLessEqual(slot.canceled_at, datetime.now(timezone.utc))

    async def test_non_host_cannot_cancel_slot(self):
        slot = future_slot()

        with self.assertRaises(HTTPException) as context:
            await cancel_slot(
                slot_id=slot.id,
                user_id=7,
                session=FakeSession(slot),
            )

        self.assertEqual(context.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIsNone(slot.canceled_at)

    async def test_missing_slot_returns_not_found(self):
        with self.assertRaises(HTTPException) as context:
            await cancel_slot(
                slot_id=999,
                user_id=42,
                session=FakeSession(None),
            )

        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)

    async def test_repeated_cancellation_keeps_original_time(self):
        canceled_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        slot = future_slot(canceled_at=canceled_at)

        response = await cancel_slot(
            slot_id=slot.id,
            user_id=slot.host_id,
            session=FakeSession(slot),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(slot.canceled_at, canceled_at)


class CancelSlotHeaderTest(ConfiguredAuthTestCase):
    def test_endpoint_requires_user_header(self):
        response = TestClient(app).delete("/slots/1")

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


if __name__ == "__main__":
    unittest.main()
