import { useMemo, useState } from "react";
import { fetchMySlots, fetchSlots } from "../api";
import { formatDayOfMonth, formatWeekdayShort, localDateKey, pluralize } from "../format";
import { isAuthorized } from "../max";
import { useRequest } from "../useRequest";
import { EmptyState, ErrorState, Icon, SlotCard, SlotCardSkeleton } from "../ui";

const DAYS_AHEAD = 7;

function upcomingDays(): Date[] {
  const today = new Date();
  return Array.from({ length: DAYS_AHEAD }, (_, index) => new Date(today.getFullYear(), today.getMonth(), today.getDate() + index));
}

export default function Home({ open, create }: { open: (id: number) => void; create: () => void }) {
  const [state, retry] = useRequest(fetchSlots, []);
  const [mine] = useRequest((signal) => (isAuthorized() ? fetchMySlots(signal) : Promise.resolve([])), []);
  const [dayKey, setDayKey] = useState<string | null>(null);
  const days = useMemo(upcomingDays, []);

  const roles = useMemo(() => {
    const map = new Map<number, "host" | "participant">();
    if (mine.status === "success") mine.data.forEach((slot) => map.set(slot.id, slot.role));
    return map;
  }, [mine]);

  const slots = state.status === "success" ? state.data : [];
  const visible = dayKey ? slots.filter((slot) => localDateKey(slot.start_at) === dayKey) : slots;
  const daysWithGames = new Set(slots.map((slot) => localDateKey(slot.start_at)));

  return (
    <div className="screen">
      <div className="home-header">
        <div>
          <div className="eyebrow eyebrow--blue">ИГРЫ РЯДОМ</div>
          <div className="page-title">Найдите игру</div>
        </div>
      </div>
      <div className="date-strip">
        <div
          className={`date-pill date-pill--all${dayKey === null ? " is-active" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => setDayKey(null)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") setDayKey(null);
          }}
        >
          <span>Все</span>
          <strong>дни</strong>
        </div>
        {days.map((day) => {
          const key = localDateKey(day);
          return (
            <div
              className={`date-pill${dayKey === key ? " is-active" : ""}${daysWithGames.has(key) ? " has-games" : ""}`}
              role="button"
              tabIndex={0}
              key={key}
              onClick={() => setDayKey(key)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") setDayKey(key);
              }}
            >
              <span>{formatWeekdayShort(day)}</span>
              <strong>{formatDayOfMonth(day)}</strong>
            </div>
          );
        })}
      </div>
      <div className="section-heading">
        <div>Ближайшие игры</div>
        {state.status === "success" && visible.length > 0 && (
          <span>{visible.length} {pluralize(visible.length, ["игра", "игры", "игр"])}</span>
        )}
      </div>
      {state.status === "loading" && (
        <div className="cards" role="status" aria-busy="true" aria-label="Загрузка игр">
          <SlotCardSkeleton />
          <SlotCardSkeleton />
          <SlotCardSkeleton />
        </div>
      )}
      {state.status === "error" && <ErrorState error={state.error} retry={retry} />}
      {state.status === "success" && slots.length === 0 && (
        <EmptyState
          title="Пока нет игр"
          copy="На ближайшую неделю игр не запланировано. Создайте свою или обновите список."
          action="Обновить"
          onAction={retry}
        />
      )}
      {state.status === "success" && slots.length > 0 && visible.length === 0 && (
        <EmptyState
          title="На этот день игр нет"
          copy="Выберите другой день или создайте свою игру."
          action="Показать все дни"
          onAction={() => setDayKey(null)}
        />
      )}
      {visible.length > 0 && (
        <div className="cards">
          {visible.map((slot) => (
            <SlotCard key={slot.id} slot={slot} role={roles.get(slot.id)} onOpen={() => open(slot.id)} />
          ))}
        </div>
      )}
      <div className="fab" role="button" tabIndex={0} onClick={create} onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") create();
      }}>
        <Icon name="plus" size={22} />
        <span>Создать игру</span>
      </div>
    </div>
  );
}
