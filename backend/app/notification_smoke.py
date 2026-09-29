"""Smoke test of notification delivery.

Creates one job of every implemented type for a real MAX user and waits until
the running notification worker delivers them:

    python -m app.notification_smoke --user-id 123456789

The user must have started a dialog with the bot, otherwise MAX rejects the
messages and the jobs end up as `failed` with the API response in `last_error`.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from app.models import NotificationJob, Slot
from app.notification_worker import collect_stats


SMOKE_TYPES = (
    "joined",
    "reminder_24h",
    "reminder_2h",
    "game_status_1h",
    "slot_canceled",
    "participant_left",
)
PAYLOADS = {
    "slot_canceled": {"reason": "Проверка уведомлений (smoke-test)"},
    "participant_left": {"participant_name": "Тестовый участник"},
}
FINAL_STATUSES = {"sent", "failed", "canceled"}
POLL_INTERVAL_SECONDS = 3


async def pick_slot(slot_id: int | None) -> Slot:
    async with SessionLocal() as session:
        query = select(Slot)
        if slot_id is not None:
            query = query.where(Slot.id == slot_id)
        else:
            query = query.where(Slot.canceled_at.is_(None)).order_by(
                Slot.start_at.desc()
            )
        slot = (await session.scalars(query.limit(1))).first()

    if slot is None:
        raise SystemExit(
            "No slot found. Create a game in the mini app or pass --slot-id."
        )
    return slot


async def create_jobs(user_id: int, slot_id: int) -> list[int]:
    run_id = uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        async with session.begin():
            jobs = [
                NotificationJob(
                    slot_id=slot_id,
                    recipient_user_id=user_id,
                    notification_type=notification_type,
                    scheduled_at=now,
                    payload=PAYLOADS.get(notification_type),
                    dedupe_key=f"smoke:{run_id}:{notification_type}",
                )
                for notification_type in SMOKE_TYPES
            ]
            session.add_all(jobs)
            await session.flush()
            return [job.id for job in jobs]


async def load_jobs(job_ids: list[int]) -> list[NotificationJob]:
    async with SessionLocal() as session:
        result = await session.scalars(
            select(NotificationJob)
            .where(NotificationJob.id.in_(job_ids))
            .order_by(NotificationJob.id)
        )
        return list(result.all())


def print_report(jobs: list[NotificationJob]) -> None:
    print(f"{'id':>6}  {'type':<18} {'status':<11} {'attempts':>8}  last_error")
    for job in jobs:
        print(
            f"{job.id:>6}  {job.notification_type:<18} {job.status:<11} "
            f"{job.attempts:>8}  {job.last_error or ''}"
        )


async def run(user_id: int, slot_id: int | None, timeout: int) -> int:
    slot = await pick_slot(slot_id)
    job_ids = await create_jobs(user_id, slot.id)
    print(
        f"Created {len(job_ids)} jobs for user {user_id} on slot {slot.id}. "
        f"Waiting up to {timeout}s for the worker..."
    )

    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        jobs = await load_jobs(job_ids)
        if all(job.status in FINAL_STATUSES for job in jobs):
            break
        if asyncio.get_running_loop().time() >= deadline:
            break
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    print_report(jobs)
    print(f"Queue: {(await collect_stats(SessionLocal)).format()}")

    if all(job.status == "sent" for job in jobs):
        print("OK: all notification types were delivered.")
        return 0
    if any(job.status in {"pending", "processing"} for job in jobs):
        print("Timeout: is the notification worker running?")
    else:
        print("FAILED: see last_error above and the worker logs.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--user-id", type=int, required=True, help="MAX user id")
    parser.add_argument("--slot-id", type=int, help="slot to use (default: newest)")
    parser.add_argument("--timeout", type=int, default=120, help="seconds to wait")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.user_id, args.slot_id, args.timeout)))


if __name__ == "__main__":
    main()
