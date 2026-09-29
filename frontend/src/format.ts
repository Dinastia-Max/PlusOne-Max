const LOCALE = "ru-RU";

type DateInput = string | Date;

const timeFormat = new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit" });
const dateFormat = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long" });
const weekdayFormat = new Intl.DateTimeFormat(LOCALE, { weekday: "long" });
const weekdayShortFormat = new Intl.DateTimeFormat(LOCALE, { weekday: "short" });
const monthShortFormat = new Intl.DateTimeFormat(LOCALE, { month: "short" });
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

function toDate(value: DateInput): Date {
  return value instanceof Date ? value : new Date(value);
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function formatTimeRange(startAt: DateInput, endAt: DateInput): string {
  return `${timeFormat.format(toDate(startAt))}–${timeFormat.format(toDate(endAt))}`;
}

export function formatDayLabel(value: DateInput, now: Date = new Date()): string {
  const date = toDate(value);
  const diffDays = Math.round((startOfDay(date) - startOfDay(now)) / 86_400_000);
  if (diffDays === 0) return "Сегодня";
  if (diffDays === 1) return "Завтра";
  return capitalize(weekdayFormat.format(date));
}

export function formatDate(value: DateInput): string {
  return dateFormat.format(toDate(value));
}

export function formatDateTime(value: DateInput): string {
  return dateTimeFormat.format(toDate(value));
}

export function formatWeekdayShort(value: DateInput): string {
  return capitalize(weekdayShortFormat.format(toDate(value)).replace(".", ""));
}

export function formatMonthShort(value: DateInput): string {
  return monthShortFormat.format(toDate(value)).replace(".", "").toUpperCase();
}

export function formatDayOfMonth(value: DateInput): string {
  return String(toDate(value).getDate());
}

export function localDateKey(value: DateInput): string {
  const date = toDate(value);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function localTimeValue(value: DateInput): string {
  const date = toDate(value);
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function pluralize(count: number, forms: [one: string, few: string, many: string]): string {
  const mod100 = Math.abs(count) % 100;
  const mod10 = mod100 % 10;
  if (mod100 > 10 && mod100 < 20) return forms[2];
  if (mod10 === 1) return forms[0];
  if (mod10 >= 2 && mod10 <= 4) return forms[1];
  return forms[2];
}

export function formatFreeSeats(free: number): string {
  if (free <= 0) return "Мест нет";
  return `${free} ${pluralize(free, ["свободное место", "свободных места", "свободных мест"])}`;
}

export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} мин`;
  return rest === 0 ? `${hours} ч` : `${hours} ч ${rest} мин`;
}
