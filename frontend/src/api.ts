import { API_URL } from "./config";
import { getInitData } from "./max";

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
  is_host: boolean;
};

export type UserSlot = SlotListItem & {
  role: "host" | "participant";
};

export type Participant = {
  is_current_user: boolean;
  brings_ball: boolean;
  joined_at: string;
};

export type HostContact = {
  type: "max" | "phone" | "none";
  label: string | null;
  href: string | null;
};

export type SlotCreate = {
  field_id: number;
  start_at: string;
  end_at: string;
  min_players: number;
  max_players: number;
  has_ball: boolean;
  host_contact_type: "max" | "phone" | "none";
  host_phone: string | null;
};

export type ApiErrorKind =
  | "network"
  | "unauthorized"
  | "not_found"
  | "forbidden"
  | "conflict"
  | "validation"
  | "server";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;

  constructor(kind: ApiErrorKind, message: string, status?: number) {
    super(message);
    this.kind = kind;
    this.status = status;
  }
}

const AUTH_MESSAGE = "Откройте приложение из MAX, чтобы войти.";

const DETAIL_MESSAGES: Record<string, string> = {
  "Slot not found": "Игра не найдена. Возможно, её отменили.",
  "Active field not found": "Эта площадка недоступна. Выберите другую.",
  "Slot is canceled": "Игру отменили.",
  "Slot has already started": "Игра уже началась.",
  "User has already joined this slot": "Вы уже записаны на эту игру.",
  "User has an overlapping slot": "У вас уже есть игра в это время.",
  "Slot is full": "Свободных мест не осталось.",
  "Only the host can cancel this slot": "Отменить игру может только организатор.",
  "Participation not found": "Вы не записаны на эту игру.",
  "Host cannot leave own slot": "Организатор не может выйти из своей игры.",
  "Participants are available to game members only": "Состав доступен только участникам игры.",
  "Slot must start in the future": "Игра должна начинаться в будущем.",
  "Invalid or expired MAX init data": AUTH_MESSAGE,
  "MAX authentication is not configured": "Сервер пока не настроен для входа через MAX.",
};

function kindForStatus(status: number): ApiErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422) return "validation";
  return "server";
}

async function toApiError(response: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = ((await response.json()) as { detail?: unknown }).detail;
  } catch {
    detail = undefined;
  }

  const kind = kindForStatus(response.status);
  const known = typeof detail === "string" ? DETAIL_MESSAGES[detail] : undefined;
  if (known) return new ApiError(kind, known, response.status);
  if (kind === "unauthorized") return new ApiError(kind, AUTH_MESSAGE, response.status);
  if (kind === "validation") return new ApiError(kind, "Проверьте введённые данные.", response.status);
  return new ApiError(kind, `Ошибка сервера (${response.status})`, response.status);
}

async function request<T>(
  path: string,
  { method = "GET", body, signal }: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const headers = new Headers({ Accept: "application/json" });
  const initData = getInitData();
  if (initData) headers.set("X-Max-Init-Data", initData);
  if (body !== undefined) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("network", "Сервер недоступен");
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;

  try {
    return (await response.json()) as T;
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("server", "Сервер вернул некорректный ответ", response.status);
  }
}

async function requestList<T>(path: string, signal?: AbortSignal): Promise<T[]> {
  const data = await request<T[]>(path, { signal });
  if (!Array.isArray(data)) throw new ApiError("server", "Сервер вернул некорректный ответ");
  return data;
}

export function fetchSlots(signal?: AbortSignal): Promise<SlotListItem[]> {
  return requestList<SlotListItem>("/slots", signal);
}

export function fetchSlot(id: number, signal?: AbortSignal): Promise<SlotDetail> {
  return request<SlotDetail>(`/slots/${id}`, { signal });
}

export function fetchParticipants(id: number, signal?: AbortSignal): Promise<Participant[]> {
  return requestList<Participant>(`/slots/${id}/participants`, signal).catch((error: unknown) => {
    if (error instanceof ApiError && (error.kind === "unauthorized" || error.kind === "forbidden")) return [];
    throw error;
  });
}

export function fetchHostContact(id: number, signal?: AbortSignal): Promise<HostContact> {
  return request<HostContact>(`/slots/${id}/host-contact`, { signal });
}

export function fetchMySlots(signal?: AbortSignal): Promise<UserSlot[]> {
  return requestList<UserSlot>("/users/me/slots", signal);
}

export function fetchFields(signal?: AbortSignal): Promise<Field[]> {
  return requestList<Field>("/fields", signal);
}

export function createSlot(data: SlotCreate): Promise<SlotDetail> {
  return request<SlotDetail>("/slots", { method: "POST", body: data });
}

export function joinSlot(id: number): Promise<void> {
  return request<void>(`/slots/${id}/join`, { method: "POST" });
}

export function leaveSlot(id: number): Promise<void> {
  return request<void>(`/slots/${id}/join`, { method: "DELETE" });
}

export function cancelSlot(id: number): Promise<void> {
  return request<void>(`/slots/${id}`, { method: "DELETE" });
}
