const LOCALE = "ru-RU";

const timeFormat = new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit" });
const dateFormat = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long" });
const weekdayFormat = new Intl.DateTimeFormat(LOCALE, { weekday: "long" });
const monthShortFormat = new Intl.DateTimeFormat(LOCALE, { month: "short" });

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatTimeRange(startAt: string, endAt: string): string {
  return `${timeFormat.format(new Date(startAt))}–${timeFormat.format(new Date(endAt))}`;
}

export function formatDayLabel(startAt: string, now: Date = new Date()): string {
  const start = new Date(startAt);
  const diffDays = Math.round((startOfDay(start) - startOfDay(now)) / 86_400_000);
  if (diffDays === 0) return "Сегодня";
  if (diffDays === 1) return "Завтра";
  return capitalize(weekdayFormat.format(start));
}

export function formatDate(startAt: string): string {
  return dateFormat.format(new Date(startAt));
}

export function formatMonthShort(startAt: string): string {
  return monthShortFormat.format(new Date(startAt)).replace(".", "").toUpperCase();
}

export function formatDayOfMonth(startAt: string): string {
  return String(new Date(startAt).getDate());
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
