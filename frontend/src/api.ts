import { API_URL } from "./config";

export type Field = {
  id: number;
  name: string;
  address: string;
  district: string;
};

export type SlotListItem = {
  id: number;
  start_at: string;
  end_at: string;
  max_players: number;
  participants_count: number;
  has_ball: boolean;
  field: Field;
};

export type SlotDetail = SlotListItem & {
  min_players: number;
  host_id: number;
};

export type ApiErrorKind = "network" | "not_found" | "server";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;

  constructor(kind: ApiErrorKind, message: string, status?: number) {
    super(message);
    this.kind = kind;
    this.status = status;
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  const headers = new Headers({ Accept: "application/json" });
  const initData = (
    window as unknown as { WebApp?: { initData?: string } }
  ).WebApp?.initData;
  if (initData) headers.set("X-Max-Init-Data", initData);

  try {
    response = await fetch(`${API_URL}${path}`, { signal, headers });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("network", "Сервер недоступен");
  }

  if (response.status === 404) throw new ApiError("not_found", "Не найдено", 404);
  if (!response.ok) throw new ApiError("server", `Ошибка сервера (${response.status})`, response.status);

  try {
    return (await response.json()) as T;
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("server", "Сервер вернул некорректный ответ", response.status);
  }
}

export async function fetchSlots(signal?: AbortSignal): Promise<SlotListItem[]> {
  const data = await getJson<SlotListItem[]>("/slots", signal);
  if (!Array.isArray(data)) throw new ApiError("server", "Сервер вернул некорректный ответ");
  return data;
}

export function fetchSlot(id: number, signal?: AbortSignal): Promise<SlotDetail> {
  return getJson<SlotDetail>(`/slots/${id}`, signal);
}
