from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255))
    district: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="valid_time_range"),
        CheckConstraint("min_players > 0", name="positive_min_players"),
        CheckConstraint(
            "max_players >= min_players",
            name="valid_player_limits",
        ),
        Index("ix_slots_start_at", "start_at"),
        Index("ix_slots_field_time", "field_id", "start_at", "end_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(
        ForeignKey("fields.id", ondelete="RESTRICT"),
        nullable=False,
    )
    host_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    min_players: Mapped[int] = mapped_column(Integer, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)
    has_ball: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    host_contact: Mapped[str | None] = mapped_column(String(255))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Participation(Base):
    __tablename__ = "participations"
    __table_args__ = (Index("ix_participations_user_id", "user_id"),)

    slot_id: Mapped[int] = mapped_column(
        ForeignKey("slots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    brings_ball: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class NotificationJob(Base):
    __tablename__ = "notification_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'failed', 'canceled')",
            name="valid_status",
        ),
        CheckConstraint("attempts >= 0", name="non_negative_attempts"),
        Index("ix_notification_jobs_status_scheduled", "status", "scheduled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    payload: Mapped[dict | None] = mapped_column(JSON)
    dedupe_key: Mapped[str | None] = mapped_column(
        String(160),
        unique=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
