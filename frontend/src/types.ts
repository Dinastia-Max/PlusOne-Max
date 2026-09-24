export interface Field {
  id: number;
  name: string;
  address: string;
  district: string;
}

export interface SlotListItem {
  id: number;
  start_at: string;
  end_at: string;
  max_players: number;
  participants_count: number;
  has_ball: boolean;
  field: Field;
}

export interface SlotDetail extends SlotListItem {
  min_players: number;
  host_id: number;
}
