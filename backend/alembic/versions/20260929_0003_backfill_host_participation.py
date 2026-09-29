"""Backfill slot hosts as participants."""

from collections.abc import Sequence

from alembic import op


revision: str = "20260929_0003"
down_revision: str | None = "20260928_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO participations (slot_id, user_id, brings_ball)
        SELECT id, host_id, has_ball
        FROM slots
        ON CONFLICT (slot_id, user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    # Existing and backfilled host participations are indistinguishable.
    # Keep participation data intact on downgrade.
    pass
