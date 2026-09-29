import re
from datetime import datetime
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class FieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    district: str


class SlotListItem(BaseModel):
    id: int
    start_at: datetime
    end_at: datetime
    max_players: int
    participants_count: int
    has_ball: bool
    field: FieldResponse


class UserSlotListItem(SlotListItem):
    role: Literal["host", "participant"]


class SlotDetail(SlotListItem):
    min_players: int
    host_id: int


class SlotCreate(BaseModel):
    field_id: int = Field(gt=0)
    start_at: AwareDatetime
    end_at: AwareDatetime
    min_players: int = Field(gt=0)
    max_players: int = Field(gt=0)
    has_ball: bool = False
    host_contact_type: Literal["max", "phone", "none"] = "max"
    host_phone: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        if self.max_players < self.min_players:
            raise ValueError("max_players must be greater than or equal to min_players")
        if self.host_contact_type == "phone":
            if not self.host_phone:
                raise ValueError("host_phone is required for phone contact")
            normalized_phone = re.sub(r"[\s()-]", "", self.host_phone)
            if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized_phone):
                raise ValueError("host_phone must be in international format")
            self.host_phone = normalized_phone
        else:
            self.host_phone = None
        return self


class ParticipantResponse(BaseModel):
    is_current_user: bool
    brings_ball: bool
    joined_at: datetime


class HostContactResponse(BaseModel):
    type: Literal["max", "phone", "none"]
    label: str | None = None
    href: str | None = None
