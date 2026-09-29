"""Create notification jobs table."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260929_0003"
down_revision: str | None = "20260928_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.BigInteger(), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=160), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_notification_jobs_non_negative_attempts",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'failed', 'canceled')",
            name="ck_notification_jobs_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["slots.id"],
            name="fk_notification_jobs_slot_id_slots",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification_jobs"),
        sa.UniqueConstraint(
            "dedupe_key",
            name="uq_notification_jobs_dedupe_key",
        ),
    )
    op.create_index(
        "ix_notification_jobs_recipient_user_id",
        "notification_jobs",
        ["recipient_user_id"],
    )
    op.create_index(
        "ix_notification_jobs_slot_id",
        "notification_jobs",
        ["slot_id"],
    )
    op.create_index(
        "ix_notification_jobs_status_scheduled",
        "notification_jobs",
        ["status", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_jobs_status_scheduled",
        table_name="notification_jobs",
    )
    op.drop_index(
        "ix_notification_jobs_slot_id",
        table_name="notification_jobs",
    )
    op.drop_index(
        "ix_notification_jobs_recipient_user_id",
        table_name="notification_jobs",
    )
    op.drop_table("notification_jobs")
