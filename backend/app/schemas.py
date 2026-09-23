from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class SlotDetail(SlotListItem):
    min_players: int
    host_id: int
