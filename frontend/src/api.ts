import type { SlotDetail, SlotListItem } from "./types";


const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getSlots(): Promise<SlotListItem[]> {
  return request<SlotListItem[]>("/slots");
}

export function getSlot(slotId: number): Promise<SlotDetail> {
  return request<SlotDetail>(`/slots/${slotId}`);
}
