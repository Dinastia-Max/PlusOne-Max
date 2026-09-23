"""Create fields, slots and participations tables."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260923_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("district", sa.String(length=120), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fields"),
    )

    op.create_table(
        "slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("host_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("min_players", sa.Integer(), nullable=False),
        sa.Column("max_players", sa.Integer(), nullable=False),
        sa.Column(
            "has_ball",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("host_contact", sa.String(length=255), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "end_at > start_at",
            name="ck_slots_valid_time_range",
        ),
        sa.CheckConstraint(
            "min_players > 0",
            name="ck_slots_positive_min_players",
        ),
        sa.CheckConstraint(
            "max_players >= min_players",
            name="ck_slots_valid_player_limits",
        ),
        sa.ForeignKeyConstraint(
            ["field_id"],
            ["fields.id"],
            name="fk_slots_field_id_fields",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_slots"),
    )
    op.create_index(
        "ix_slots_field_time",
        "slots",
        ["field_id", "start_at", "end_at"],
    )
    op.create_index("ix_slots_host_id", "slots", ["host_id"])
    op.create_index("ix_slots_start_at", "slots", ["start_at"])

    op.create_table(
        "participations",
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "brings_ball",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["slots.id"],
            name="fk_participations_slot_id_slots",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "slot_id",
            "user_id",
            name="pk_participations",
        ),
    )
    op.create_index(
        "ix_participations_user_id",
        "participations",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_participations_user_id", table_name="participations")
    op.drop_table("participations")
    op.drop_index("ix_slots_start_at", table_name="slots")
    op.drop_index("ix_slots_host_id", table_name="slots")
    op.drop_index("ix_slots_field_time", table_name="slots")
    op.drop_table("slots")
    op.drop_table("fields")
