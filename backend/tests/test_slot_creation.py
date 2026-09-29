import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.models import Field, NotificationJob, Participation, Slot
from app.routers.slots import create_slot
from app.schemas import SlotCreate


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
    def __init__(self, field, overlapping_slot_id=None):
        self.field = field
        self.overlapping_slot_id = overlapping_slot_id
        self.scalar_statements = []
        self.added = []

    def begin(self):
        return TransactionContext()

    async def execute(self, statement):
        return FakeResult(self.field)

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return self.overlapping_slot_id

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.added[0].id = 100


def valid_slot_data(**overrides) -> SlotCreate:
    start_at = datetime.now(timezone.utc) + timedelta(days=1)
    values = {
        "field_id": 1,
        "start_at": start_at,
        "end_at": start_at + timedelta(hours=2),
        "min_players": 6,
        "max_players": 12,
        "has_ball": True,
    }
    values.update(overrides)
    return SlotCreate(**values)


class CreateSlotTest(unittest.IsolatedAsyncioTestCase):
    async def test_user_can_create_slot(self):
        field = Field(
            id=1,
            name="Test field",
            address="Test address",
            district="Test district",
            is_active=True,
        )
        session = FakeSession(field)
        slot_data = valid_slot_data()

        response = await create_slot(
            slot_data_in=slot_data,
            user_id=42,
            session=session,
        )

        self.assertEqual(response.id, 100)
        self.assertTrue(response.is_host)
        self.assertEqual(response.participants_count, 1)
        self.assertEqual(response.field.id, 1)
        self.assertIsInstance(session.added[0], Slot)
        participation = next(
            value
            for value in session.added
            if isinstance(value, Participation)
        )
        self.assertEqual(participation.slot_id, 100)
        self.assertEqual(participation.user_id, 42)
        self.assertTrue(participation.brings_ball)
        self.assertIsNone(session.added[0].host_contact)
        self.assertIn("pg_advisory_xact_lock", str(session.scalar_statements[0]))
        notifications = [
            value
            for value in session.added
            if isinstance(value, NotificationJob)
        ]
        self.assertEqual(
            {job.notification_type for job in notifications},
            {"reminder_2h", "game_status_1h"},
        )

    async def test_phone_contact_is_normalized_and_saved(self):
        field = Field(
            id=1,
            name="Test field",
            address="Test address",
            district="Test district",
            is_active=True,
        )
        session = FakeSession(field)

        await create_slot(
            slot_data_in=valid_slot_data(
                host_contact_type="phone",
                host_phone="+7 (999) 123-45-67",
            ),
            user_id=42,
            session=session,
        )

        self.assertEqual(session.added[0].host_contact, "tel:+79991234567")

    async def test_host_cannot_create_overlapping_slot(self):
        field = Field(
            id=1,
            name="Test field",
            address="Test address",
            district="Test district",
            is_active=True,
        )
        session = FakeSession(field, overlapping_slot_id=99)

        with self.assertRaises(HTTPException) as context:
            await create_slot(
                slot_data_in=valid_slot_data(),
                user_id=42,
                session=session,
            )

        self.assertEqual(context.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(context.exception.detail, "User has an overlapping slot")
        self.assertEqual(session.added, [])

    async def test_active_field_is_required(self):
        session = FakeSession(None)

        with self.assertRaises(HTTPException) as context:
            await create_slot(
                slot_data_in=valid_slot_data(),
                user_id=42,
                session=session,
            )

        self.assertEqual(context.exception.status_code, status.HTTP_404_NOT_FOUND)

    async def test_slot_must_start_in_future(self):
        start_at = datetime.now(timezone.utc) - timedelta(hours=2)
        slot_data = valid_slot_data(
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
        )

        with self.assertRaises(HTTPException) as context:
            await create_slot(
                slot_data_in=slot_data,
                user_id=42,
                session=FakeSession(None),
            )

        self.assertEqual(
            context.exception.status_code,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


class SlotCreateSchemaTest(unittest.TestCase):
    def test_phone_contact_requires_valid_international_phone(self):
        with self.assertRaises(ValidationError):
            valid_slot_data(host_contact_type="phone")

        with self.assertRaises(ValidationError):
            valid_slot_data(host_contact_type="phone", host_phone="89991234567")

    def test_phone_is_discarded_for_non_phone_contact(self):
        slot_data = valid_slot_data(
            host_contact_type="none",
            host_phone="+79991234567",
        )

        self.assertIsNone(slot_data.host_phone)

    def test_contact_is_not_set_by_default(self):
        self.assertEqual(valid_slot_data().host_contact_type, "none")

    def test_max_profile_contact_is_not_supported(self):
        with self.assertRaises(ValidationError):
            valid_slot_data(host_contact_type="max")

    def test_end_must_be_later_than_start(self):
        start_at = datetime.now(timezone.utc) + timedelta(days=1)

        with self.assertRaises(ValidationError):
            valid_slot_data(start_at=start_at, end_at=start_at)

    def test_player_limits_must_be_valid(self):
        with self.assertRaises(ValidationError):
            valid_slot_data(min_players=12, max_players=6)

        with self.assertRaises(ValidationError):
            valid_slot_data(min_players=0)

    def test_time_zone_is_required(self):
        start_at = datetime.now() + timedelta(days=1)

        with self.assertRaises(ValidationError):
            valid_slot_data(
                start_at=start_at,
                end_at=start_at + timedelta(hours=2),
            )


if __name__ == "__main__":
    unittest.main()
