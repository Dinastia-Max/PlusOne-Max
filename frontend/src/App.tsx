import { useEffect, useMemo, useState } from "react";
import { Link, Route, Routes, useParams } from "react-router-dom";

import { getSlot, getSlots } from "./api";
import type { SlotDetail, SlotListItem } from "./types";


const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  weekday: "long",
  day: "numeric",
  month: "long",
});

const compactDateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
});

const timeFormatter = new Intl.DateTimeFormat("ru-RU", {
  hour: "2-digit",
  minute: "2-digit",
});

function formatTimeRange(startAt: string, endAt: string): string {
  return `${timeFormatter.format(new Date(startAt))}–${timeFormatter.format(new Date(endAt))}`;
}

function formatDate(value: string): string {
  const formatted = dateFormatter.format(new Date(value));
  return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

function Header({ compact = false }: { compact?: boolean }) {
  return (
    <header className={compact ? "app-header compact" : "app-header"}>
      <div className="brand-mark" aria-hidden="true">+1</div>
      <div className="brand-copy">
        <strong>ПлюсОдин</strong>
        <span>Футбол рядом</span>
      </div>
      <div className="district-pill">Хорошёвский</div>
    </header>
  );
}

function LoadingState() {
  return (
    <div className="state-card" role="status">
      <div className="spinner" aria-hidden="true" />
      <strong>Ищем ближайшие игры</strong>
      <span>Это займёт пару секунд</span>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="state-card error-card" role="alert">
      <div className="state-icon">!</div>
      <strong>Не удалось загрузить игры</strong>
      <span>Проверьте соединение и попробуйте ещё раз</span>
      <button className="secondary-button" type="button" onClick={onRetry}>Повторить</button>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="state-card empty-card">
      <div className="ball-orbit" aria-hidden="true">⚽</div>
      <strong>Пока нет новых игр</strong>
      <span>Загляните позже или создайте первую игру в районе</span>
      <button className="primary-button" type="button" disabled>Создание скоро</button>
    </div>
  );
}

function SlotCard({ slot }: { slot: SlotListItem }) {
  const placesLeft = Math.max(slot.max_players - slot.participants_count, 0);

  return (
    <Link className="slot-card" to={`/slot/${slot.id}`}>
      <div className="slot-date">
        <span>{compactDateFormatter.format(new Date(slot.start_at))}</span>
        <strong>{formatTimeRange(slot.start_at, slot.end_at)}</strong>
      </div>
      <div className="slot-main">
        <div className="slot-title-row">
          <h2>{slot.field.name}</h2>
          <span className="arrow" aria-hidden="true">↗</span>
        </div>
        <p>{slot.field.address}</p>
        <div className="slot-meta">
          <span className="players-chip"><b>{slot.participants_count}</b>/{slot.max_players} игроков</span>
          {slot.has_ball && <span className="ball-chip">Мяч есть</span>}
          <span className={placesLeft > 0 ? "places open" : "places full"}>
            {placesLeft > 0 ? `${placesLeft} мест` : "Мест нет"}
          </span>
        </div>
      </div>
    </Link>
  );
}

function SlotsPage() {
  const [slots, setSlots] = useState<SlotListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadSlots = () => {
    setLoading(true);
    setError(false);
    getSlots()
      .then(setSlots)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(loadSlots, []);

  const groupedSlots = useMemo(() => {
    return slots.reduce<Map<string, SlotListItem[]>>((groups, slot) => {
      const key = new Date(slot.start_at).toDateString();
      const daySlots = groups.get(key) ?? [];
      daySlots.push(slot);
      groups.set(key, daySlots);
      return groups;
    }, new Map());
  }, [slots]);

  return (
    <main className="app-shell">
      <Header />
      <section className="hero">
        <div>
          <span className="eyebrow">Москва · ближайшие 7 дней</span>
          <h1>Игры рядом</h1>
          <p>Выберите время и присоединяйтесь без долгих переписок.</p>
        </div>
        <div className="hero-ball" aria-hidden="true"><span>⚽</span></div>
      </section>

      <section className="content-section">
        <div className="section-heading">
          <h2>Ближайшие игры</h2>
          {!loading && !error && slots.length > 0 && <span>{slots.length}</span>}
        </div>

        {loading && <LoadingState />}
        {!loading && error && <ErrorState onRetry={loadSlots} />}
        {!loading && !error && slots.length === 0 && <EmptyState />}

        {!loading && !error && slots.length > 0 && (
          <div className="slot-groups">
            {Array.from(groupedSlots.entries()).map(([day, daySlots]) => (
              <div className="slot-group" key={day}>
                <h3>{formatDate(daySlots[0].start_at)}</h3>
                <div className="slot-list">
                  {daySlots.map((slot) => <SlotCard key={slot.id} slot={slot} />)}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
      <footer>Сделано для быстрых игр в вашем районе</footer>
    </main>
  );
}

function SlotDetailPage() {
  const { slotId } = useParams();
  const [slot, setSlot] = useState<SlotDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const numericSlotId = Number(slotId);
    if (!Number.isInteger(numericSlotId)) {
      setError(true);
      setLoading(false);
      return;
    }

    getSlot(numericSlotId)
      .then(setSlot)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [slotId]);

  return (
    <main className="app-shell detail-shell">
      <Header compact />
      <Link className="back-link" to="/"><span aria-hidden="true">←</span> Все игры</Link>

      {loading && <LoadingState />}
      {!loading && error && (
        <div className="state-card error-card">
          <div className="state-icon">!</div>
          <strong>Игра не найдена</strong>
          <span>Возможно, слот был отменён или уже завершился</span>
          <Link className="secondary-button link-button" to="/">Вернуться к списку</Link>
        </div>
      )}

      {!loading && slot && (
        <article className="detail-card">
          <div className="detail-kicker">Футбол · {slot.field.district}</div>
          <h1>{slot.field.name}</h1>
          <p className="detail-address">{slot.field.address}</p>

          <div className="detail-time-block">
            <span>{formatDate(slot.start_at)}</span>
            <strong>{formatTimeRange(slot.start_at, slot.end_at)}</strong>
          </div>

          <div className="detail-grid">
            <div><span>Участники</span><strong>{slot.participants_count}/{slot.max_players}</strong></div>
            <div><span>Минимум</span><strong>{slot.min_players}</strong></div>
            <div><span>Мяч</span><strong>{slot.has_ball ? "Есть" : "Нужен"}</strong></div>
          </div>

          <div className="host-row">
            <div className="host-avatar">Х</div>
            <div><span>Организатор</span><strong>Хост игры #{slot.host_id}</strong></div>
          </div>

          <button className="primary-button join-button" type="button" disabled>Запись скоро появится</button>
          <p className="button-note">Пока слот доступен только для просмотра</p>
        </article>
      )}
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SlotsPage />} />
      <Route path="/slot/:slotId" element={<SlotDetailPage />} />
      <Route path="*" element={<SlotsPage />} />
    </Routes>
  );
}
