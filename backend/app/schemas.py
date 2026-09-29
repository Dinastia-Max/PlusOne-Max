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
    host_participates: bool = True

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        if self.max_players < self.min_players:
            raise ValueError("max_players must be greater than or equal to min_players")
        return self


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    brings_ball: bool
    joined_at: datetime
