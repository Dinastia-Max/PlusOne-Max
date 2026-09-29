import { fetchParticipants, fetchSlot, type Participant, type SlotDetail, type SlotListItem } from "./api";
import { useRequest } from "./useRequest";

export type SlotBundle = { slot: SlotDetail; participants: Participant[] };

export function useSlotBundle(id: number) {
  return useRequest<SlotBundle>(
    async (signal) => {
      const [slot, participants] = await Promise.all([fetchSlot(id, signal), fetchParticipants(id, signal)]);
      return { slot, participants };
    },
    [id],
  );
}

export function hasStarted(slot: SlotListItem): boolean {
  return new Date(slot.start_at).getTime() <= Date.now();
}

export function hasEnded(slot: SlotListItem): boolean {
  return new Date(slot.end_at).getTime() <= Date.now();
}

export function isFull(slot: SlotListItem): boolean {
  return slot.participants_count >= slot.max_players;
}

export function slotStatus(slot: SlotListItem): { label: string; open: boolean } {
  if (hasEnded(slot)) return { label: "Игра завершена", open: false };
  if (hasStarted(slot)) return { label: "Игра идёт", open: false };
  if (isFull(slot)) return { label: "Мест нет", open: false };
  return { label: "Набор открыт", open: true };
}
