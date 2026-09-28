import { useState, type ReactNode } from "react";
import { fetchSlot, fetchSlots, type ApiError, type SlotDetail, type SlotListItem } from "./api";
import {
  formatDate,
  formatDayLabel,
  formatDayOfMonth,
  formatFreeSeats,
  formatMonthShort,
  formatTimeRange,
  pluralize,
} from "./format";
import { useRequest } from "./useRequest";

type Screen = "onboarding" | "home" | "details" | "create" | "my" | "profile" | "manage";
type Sheet = "join" | "leave" | "success" | "message" | "cancel" | null;
type IconName =
  | "back"
  | "ball"
  | "calendar"
  | "check"
  | "chevron"
  | "clock"
  | "close"
  | "home"
  | "location"
  | "message"
  | "phone"
  | "plus"
  | "profile"
  | "shield"
  | "team"
  | "warning";

const FIELD_TONES = ["mint", "sky", "violet"] as const;

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    back: <path d="m15 18-6-6 6-6" />,
    ball: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m9.2 8.8 2.8-2 2.8 2-1.1 3.2h-3.4L9.2 8.8Zm-5.5 1.5 2.8 2.1-1 3.4m14.8-5.5-2.8 2.1 1 3.4M9.4 20l1.1-3.3h3L14.6 20" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="3" />
        <path d="M8 3v4m8-4v4M3 10h18" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    close: <path d="M6 6l12 12M18 6 6 18" />,
    home: (
      <>
        <path d="m3 11 9-8 9 8" />
        <path d="M5 10v10h14V10M9 20v-6h6v6" />
      </>
    ),
    location: (
      <>
        <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
        <circle cx="12" cy="10" r="2.5" />
      </>
    ),
    message: (
      <>
        <path d="M20 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h9a4 4 0 0 1 4 4v8Z" />
        <path d="M8 10h8M8 14h5" />
      </>
    ),
    phone: <path d="M8 3 5 4.5c-1 1-.2 5.3 3.4 8.9s7.9 4.4 8.9 3.4l1.5-3-4.2-2-1.4 1.7c-1.6-.7-3.9-3-4.6-4.6l1.7-1.4L8 3Z" />,
    plus: <path d="M12 5v14M5 12h14" />,
    profile: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21a8 8 0 0 1 16 0" />
      </>
    ),
    shield: <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Zm-3-10 2 2 4-5" />,
    team: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 19a6 6 0 0 1 12 0m1-14a3 3 0 0 1 0 6m2 2a5 5 0 0 1 3 4.6" />
      </>
    ),
    warning: (
      <>
        <path d="M10.3 3.6 2.7 17a2 2 0 0 0 1.8 3h15a2 2 0 0 0 1.8-3L13.7 3.6a2 2 0 0 0-3.4 0Z" />
        <path d="M12 8v5m0 3h.01" />
      </>
    ),
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function Button({
  children,
  onClick,
  kind = "primary",
  icon,
  disabled = false,
}: {
  children: ReactNode;
  onClick?: () => void;
  kind?: "primary" | "secondary" | "danger" | "ghost";
  icon?: IconName;
  disabled?: boolean;
}) {
  return (
    <div
      className={`button button--${kind}${disabled ? " is-disabled" : ""}`}
      role="button"
      tabIndex={disabled ? -1 : 0}
      onClick={disabled ? undefined : onClick}
      onKeyDown={(event) => {
        if (!disabled && (event.key === "Enter" || event.key === " ")) onClick?.();
      }}
    >
      {icon && <Icon name={icon} size={19} />}
      <span>{children}</span>
    </div>
  );
}

function Avatar({ name, tone = "blue", large = false }: { name: string; tone?: string; large?: boolean }) {
  const initials = name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("");
  return <div className={`avatar avatar--${tone}${large ? " avatar--large" : ""}`}>{initials}</div>;
}

function TopBar({ title, back, action }: { title: string; back?: () => void; action?: ReactNode }) {
  return (
    <div className="topbar">
      <div className="topbar__side">
        {back && (
          <div className="icon-button" role="button" tabIndex={0} onClick={back}>
            <Icon name="back" />
          </div>
        )}
      </div>
      <div className="topbar__title">{title}</div>
      <div className="topbar__side topbar__side--end">{action}</div>
    </div>
  );
}

function BottomNav({ active, navigate }: { active: Screen; navigate: (screen: Screen) => void }) {
  const items: { screen: Screen; icon: IconName; label: string }[] = [
    { screen: "home", icon: "home", label: "Игры" },
    { screen: "my", icon: "calendar", label: "Мои игры" },
    { screen: "profile", icon: "profile", label: "Профиль" },
  ];
  return (
    <div className="bottom-nav">
      {items.map((item) => (
        <div
          className={`nav-item${active === item.screen ? " is-active" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => navigate(item.screen)}
          key={item.screen}
        >
          <Icon name={item.icon} size={22} />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

function ProgressRing({ value, max }: { value: number; max: number }) {
  const share = max > 0 ? Math.min(value / max, 1) : 0;
  return (
    <div className="progress-ring" style={{ "--progress": `${share * 360}deg` } as React.CSSProperties}>
      <div>{value}</div>
      <span>из {max}</span>
    </div>
  );
}

function SlotCard({ slot, onOpen }: { slot: SlotListItem; onOpen: () => void }) {
  const tone = FIELD_TONES[slot.field.id % FIELD_TONES.length];
  return (
    <div
      className="slot-card"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      <div className="slot-card__top">
        <div>
          <div className="date-line">
            <span className="date-line__day">{formatDayLabel(slot.start_at)}</span>
            <span>{formatDate(slot.start_at)}</span>
          </div>
          <div className="slot-card__time">{formatTimeRange(slot.start_at, slot.end_at)}</div>
        </div>
        <ProgressRing value={slot.participants_count} max={slot.max_players} />
      </div>
      <div className="field-line">
        <div className={`field-icon field-icon--${tone}`}>
          <Icon name="location" size={19} />
        </div>
        <div>
          <div className="field-line__name">{slot.field.name}</div>
          <div className="field-line__address">{slot.field.address}</div>
        </div>
      </div>
      <div className="slot-card__footer">
        <div className="seats">{formatFreeSeats(slot.max_players - slot.participants_count)}</div>
        <div className="tags">
          {slot.has_ball && (
            <div className="tag">
              <Icon name="ball" size={15} />
              Мяч будет
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function errorMessage(error: ApiError): { title: string; copy: string } {
  if (error.kind === "network") {
    return { title: "Сервер недоступен", copy: "Проверьте подключение к интернету и попробуйте ещё раз." };
  }
  if (error.kind === "not_found") {
    return { title: "Игра не найдена", copy: "Возможно, её отменили или удалили." };
  }
  return { title: "Не удалось загрузить данные", copy: `${error.message}. Попробуйте ещё раз чуть позже.` };
}

function ErrorState({ error, retry }: { error: ApiError; retry: () => void }) {
  const { title, copy } = errorMessage(error);
  return (
    <div className="state-card" role="alert">
      <div className="state-card__icon state-card__icon--danger"><Icon name="warning" size={25} /></div>
      <div className="state-card__title">{title}</div>
      <div className="state-card__copy">{copy}</div>
      <Button kind="secondary" onClick={retry}>Повторить</Button>
    </div>
  );
}

function EmptyState({ refresh }: { refresh: () => void }) {
  return (
    <div className="state-card">
      <div className="state-card__icon"><Icon name="ball" size={25} /></div>
      <div className="state-card__title">Пока нет игр</div>
      <div className="state-card__copy">На ближайшую неделю игр не запланировано. Загляните позже или обновите список.</div>
      <Button kind="secondary" onClick={refresh}>Обновить</Button>
    </div>
  );
}

function SlotCardSkeleton() {
  return (
    <div className="slot-card slot-card--skeleton" aria-hidden="true">
      <div className="skeleton skeleton--line" style={{ width: "35%" }} />
      <div className="skeleton skeleton--title" style={{ width: "55%" }} />
      <div className="skeleton skeleton--line" style={{ width: "80%", marginTop: 22 }} />
      <div className="skeleton skeleton--line" style={{ width: "50%" }} />
    </div>
  );
}

function InfoRow({ icon, label, value, sub }: { icon: IconName; label: string; value: string; sub?: string }) {
  return (
    <div className="info-row">
      <div className="info-row__icon">
        <Icon name={icon} />
      </div>
      <div className="info-row__content">
        <div className="info-row__label">{label}</div>
        <div className="info-row__value">{value}</div>
        {sub && <div className="info-row__sub">{sub}</div>}
      </div>
    </div>
  );
}

function Onboarding({ start }: { start: () => void }) {
  return (
    <div className="onboarding">
      <div className="onboarding__hero">
        <div className="brand-mark">
          <div className="brand-mark__one">1</div>
          <div className="brand-mark__plus">+</div>
        </div>
        <div className="eyebrow">ПЛЮСОДИН</div>
        <div className="display-title">Футбол рядом.<br />Команда найдётся.</div>
        <div className="onboarding__copy">Находите игры в своём районе или собирайте свою — без долгих переписок.</div>
      </div>
      <div className="onboarding__panel">
        <div className="profile-preview">
          <Avatar name="Алексей Морозов" tone="blue" large />
          <div>
            <div className="profile-preview__hello">Привет, Алексей!</div>
            <div className="profile-preview__source">
              <span className="verified"><Icon name="check" size={12} /></span>
              Профиль получен из MAX
            </div>
          </div>
        </div>
        <div className="permission-row">
          <div className="permission-row__icon"><Icon name="message" /></div>
          <div className="permission-row__copy">
            <div>Напоминания об играх</div>
            <span>Бот напомнит за 24 часа и перед началом</span>
          </div>
          <div className="toggle is-on"><div /></div>
        </div>
        <Button onClick={start}>Начать играть</Button>
        <div className="legal">Продолжая, вы соглашаетесь получать уведомления от бота</div>
      </div>
    </div>
  );
}

function Home({ open, create }: { open: (id: number) => void; create: () => void }) {
  const [state, retry] = useRequest(fetchSlots, []);
  return (
    <div className="screen">
      <div className="home-header">
        <div>
          <div className="eyebrow eyebrow--blue">ИГРЫ РЯДОМ</div>
          <div className="page-title">Найдите игру</div>
        </div>
      </div>
      <div className="section-heading">
        <div>Ближайшие игры</div>
        {state.status === "success" && state.data.length > 0 && (
          <span>{state.data.length} {pluralize(state.data.length, ["игра", "игры", "игр"])}</span>
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
      {state.status === "success" && state.data.length === 0 && <EmptyState refresh={retry} />}
      {state.status === "success" && state.data.length > 0 && (
        <div className="cards">
          {state.data.map((slot) => <SlotCard key={slot.id} slot={slot} onOpen={() => open(slot.id)} />)}
        </div>
      )}
      <div className="fab" role="button" tabIndex={0} onClick={create}>
        <Icon name="plus" size={22} />
        <span>Создать игру</span>
      </div>
    </div>
  );
}

function slotStatus(slot: SlotDetail): { label: string; open: boolean } {
  if (new Date(slot.start_at).getTime() <= Date.now()) return { label: "Игра уже началась", open: false };
  if (slot.participants_count >= slot.max_players) return { label: "Мест нет", open: false };
  return { label: "Набор открыт", open: true };
}

function SlotContent({ slot }: { slot: SlotDetail }) {
  const status = slotStatus(slot);
  const freeSeats = slot.max_players - slot.participants_count;
  return (
    <>
      <div className="detail-hero">
        <div className="date-badge"><span>{formatMonthShort(slot.start_at)}</span><strong>{formatDayOfMonth(slot.start_at)}</strong></div>
        <div>
          <div className="detail-hero__day">{formatDayLabel(slot.start_at)}, {formatDate(slot.start_at)}</div>
          <div className="detail-hero__time">{formatTimeRange(slot.start_at, slot.end_at)}</div>
          <div className={`status${status.open ? "" : " status--closed"}`}><span /> {status.label}</div>
        </div>
        <ProgressRing value={slot.participants_count} max={slot.max_players} />
      </div>
      <div className="detail-content">
        <div className="info-card">
          <InfoRow icon="location" label="ПОЛЕ" value={slot.field.name} sub={slot.field.address} />
          <div className="divider" />
          <InfoRow
            icon="team"
            label="УЧАСТНИКИ"
            value={`Записалось ${slot.participants_count} из ${slot.max_players}`}
            sub={`${formatFreeSeats(freeSeats)} · минимум ${slot.min_players}`}
          />
          <div className="divider" />
          <InfoRow icon="ball" label="ИНВЕНТАРЬ" value={slot.has_ball ? "Мяч будет" : "Мяча пока нет"} />
        </div>
      </div>
    </>
  );
}

function DetailsSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="Загрузка игры">
      <div className="detail-hero" aria-hidden="true">
        <div className="skeleton" style={{ width: 57, height: 64, borderRadius: 14 }} />
        <div>
          <div className="skeleton skeleton--line" style={{ width: 90 }} />
          <div className="skeleton skeleton--title" style={{ width: 130 }} />
        </div>
        <div className="skeleton" style={{ width: 54, height: 54, borderRadius: 999 }} />
      </div>
      <div className="detail-content" aria-hidden="true">
        <div className="info-card">
          <div className="info-row"><div className="skeleton" style={{ width: "100%", height: 38 }} /></div>
          <div className="info-row"><div className="skeleton" style={{ width: "100%", height: 38 }} /></div>
          <div className="info-row"><div className="skeleton" style={{ width: "100%", height: 38 }} /></div>
        </div>
      </div>
    </div>
  );
}

function Details({ slotId, back }: { slotId: number; back: () => void }) {
  const [state, retry] = useRequest((signal) => fetchSlot(slotId, signal), [slotId]);
  return (
    <div className="screen detail-screen">
      <TopBar title="Игра" back={back} />
      {state.status === "loading" && <DetailsSkeleton />}
      {state.status === "error" && (
        <div className="detail-content">
          <ErrorState error={state.error} retry={retry} />
        </div>
      )}
      {state.status === "success" && (
        <>
          <SlotContent slot={state.data} />
          <div className="sticky-action">
            <Button disabled>Записаться на игру</Button>
            <div className="sticky-action__caption">Запись на игру пока недоступна</div>
          </div>
        </>
      )}
    </div>
  );
}

function SelectRow({ label, value, icon }: { label: string; value: string; icon: IconName }) {
  return (
    <div className="select-row" role="button" tabIndex={0}>
      <div className="select-row__icon"><Icon name={icon} /></div>
      <div className="select-row__copy"><span>{label}</span><strong>{value}</strong></div>
      <Icon name="chevron" size={18} />
    </div>
  );
}

function CreateGame({ back, publish }: { back: () => void; publish: () => void }) {
  const [ball, setBall] = useState(true);
  return (
    <div className="screen create-screen">
      <TopBar title="Новая игра" back={back} />
      <div className="create-content">
        <div className="create-intro">
          <div className="create-intro__icon"><Icon name="ball" size={25} /></div>
          <div><div className="page-title">Соберите свою игру</div><span>Укажите главное — займёт меньше минуты</span></div>
        </div>
        <div className="form-section">
          <div className="form-label">ГДЕ ИГРАЕМ</div>
          <div className="form-card"><SelectRow icon="location" label="Поле" value="Стадион «Сокол»" /></div>
        </div>
        <div className="form-section">
          <div className="form-label">КОГДА</div>
          <div className="form-card">
            <SelectRow icon="calendar" label="Дата" value="Сегодня, 24 мая" />
            <div className="divider" />
            <SelectRow icon="clock" label="Начало" value="19:00" />
            <div className="divider" />
            <SelectRow icon="clock" label="Длительность" value="1 ч 30 мин" />
          </div>
        </div>
        <div className="form-section">
          <div className="form-label">КОМАНДА</div>
          <div className="counter-grid">
            <div className="counter-card"><span>Минимум</span><div><b>−</b><strong>6</strong><b>+</b></div></div>
            <div className="counter-card"><span>Максимум</span><div><b>−</b><strong>10</strong><b>+</b></div></div>
          </div>
        </div>
        <div className="form-card switch-card" role="button" tabIndex={0} onClick={() => setBall(!ball)}>
          <div className="select-row__icon"><Icon name="ball" /></div>
          <div className="select-row__copy"><strong>У меня будет мяч</strong><span>Покажем это участникам</span></div>
          <div className={`toggle${ball ? " is-on" : ""}`}><div /></div>
        </div>
        <div className="privacy-note"><Icon name="shield" size={18} /><span>Ваш телефон увидят только записавшиеся игроки</span></div>
        <Button onClick={publish}>Опубликовать игру</Button>
      </div>
    </div>
  );
}

function MyGames({ manage }: { manage: () => void }) {
  return (
    <div className="screen">
      <TopBar title="Мои игры" />
      <div className="my-summary">
        <div><strong>2</strong><span>впереди</span></div>
        <div><strong>1</strong><span>создана вами</span></div>
      </div>
      <div className="section-heading"><div>Ближайшие</div></div>
      <div className="cards">
        <div className="role-label"><span className="role-dot" /> ВЫ УЧАСТВУЕТЕ</div>
        <div className="slot-card host-slot">
          <div className="slot-card__top">
            <div><div className="date-line"><span className="date-line__day">Сегодня</span><span>24 мая</span></div><div className="slot-card__time">19:00–20:30</div></div>
            <ProgressRing value={7} max={10} />
          </div>
          <div className="field-line"><div className="field-icon field-icon--mint"><Icon name="location" size={19} /></div><div><div className="field-line__name">Стадион «Сокол»</div><div className="field-line__address">ул. Лётчика Бабушкина, 21</div></div></div>
        </div>
        <div className="role-label role-label--host"><span className="role-dot" /> ВЫ ОРГАНИЗАТОР</div>
        <div className="slot-card host-slot" role="button" tabIndex={0} onClick={manage}>
          <div className="slot-card__top">
            <div><div className="date-line"><span className="date-line__day">Воскресенье</span><span>26 мая</span></div><div className="slot-card__time">18:30–20:00</div></div>
            <ProgressRing value={5} max={10} />
          </div>
          <div className="field-line"><div className="field-icon field-icon--violet"><Icon name="location" size={19} /></div><div><div className="field-line__name">Арена «Свиблово»</div><div className="field-line__address">Тенистый пр-д, 6</div></div></div>
          <Button kind="secondary" onClick={manage}>Управлять игрой</Button>
        </div>
      </div>
    </div>
  );
}

function Manage({ back, message, cancel }: { back: () => void; message: () => void; cancel: () => void }) {
  const people = [
    ["АС", "Антон Смирнов", "Хост"],
    ["МК", "Максим Козлов", "Возьмёт мяч"],
    ["ДВ", "Даша Воронова", "Участник"],
    ["РП", "Роман Петров", "Участник"],
    ["АК", "Алина Ким", "Участник"],
  ];
  return (
    <div className="screen">
      <TopBar title="Управление игрой" back={back} />
      <div className="manage-hero">
        <div className="eyebrow eyebrow--blue">ВОСКРЕСЕНЬЕ, 26 МАЯ</div>
        <div className="page-title">18:30–20:00</div>
        <div className="location-caption"><Icon name="location" size={15} /> Арена «Свиблово»</div>
      </div>
      <div className="manage-actions">
        <Button onClick={message} icon="message">Написать всем</Button>
        <Button kind="secondary" icon="clock">Изменить игру</Button>
      </div>
      <div className="section-heading"><div>Состав</div><span>5 из 10</span></div>
      <div className="people-list">
        {people.map((person, index) => (
          <div className="person-row" key={person[1]}>
            <Avatar name={person[0]} tone={["mint", "sky", "violet", "orange", "blue"][index]} />
            <div><strong>{person[1]}</strong><span>{person[2]}</span></div>
            {index > 0 && <div className="circle-action"><Icon name="message" size={17} /></div>}
          </div>
        ))}
      </div>
      <div className="danger-zone">
        <Button kind="danger" onClick={cancel}>Отменить игру</Button>
        <span>Все участники получат уведомление</span>
      </div>
    </div>
  );
}

function Profile() {
  return (
    <div className="screen">
      <TopBar title="Профиль" />
      <div className="profile-hero">
        <Avatar name="Алексей Морозов" tone="blue" large />
        <div className="page-title">Алексей Морозов</div>
        <div className="profile-source"><span className="verified"><Icon name="check" size={12} /></span> Профиль MAX</div>
      </div>
      <div className="profile-stats">
        <div><strong>8</strong><span>игр</span></div>
        <div><strong>3</strong><span>создано</span></div>
        <div><strong>12</strong><span>часов на поле</span></div>
      </div>
      <div className="form-section profile-section">
        <div className="form-label">КОНТАКТЫ</div>
        <div className="form-card">
          <SelectRow icon="profile" label="Имя" value="Алексей Морозов" />
          <div className="divider" />
          <SelectRow icon="phone" label="Телефон" value="+7 999 123-45-67" />
        </div>
        <div className="privacy-note"><Icon name="shield" size={18} /><span>Телефон виден только игрокам тех матчей, куда вы записались</span></div>
      </div>
      <div className="form-section profile-section">
        <div className="form-label">УВЕДОМЛЕНИЯ</div>
        <div className="form-card switch-card">
          <div className="select-row__icon"><Icon name="message" /></div>
          <div className="select-row__copy"><strong>Напоминания в MAX</strong><span>До игры и при изменениях</span></div>
          <div className="toggle is-on"><div /></div>
        </div>
      </div>
    </div>
  );
}

function Modal({ type, close, confirm }: { type: Exclude<Sheet, null>; close: () => void; confirm: () => void }) {
  const [checked, setChecked] = useState(false);
  const content = {
    join: {
      icon: "ball" as IconName,
      title: "Записаться на игру?",
      copy: "Сегодня, 19:00 · Стадион «Сокол»",
      action: "Записаться",
    },
    leave: {
      icon: "warning" as IconName,
      title: "Точно отказаться?",
      copy: "До игры меньше 2 часов. Ваше место сразу вернётся в набор.",
      action: "Да, отказаться",
    },
    success: {
      icon: "check" as IconName,
      title: "Вы в игре!",
      copy: "Напомним завтра и за 2 часа до начала. До встречи на поле.",
      action: "Отлично",
    },
    message: {
      icon: "message" as IconName,
      title: "Сообщение игрокам",
      copy: "Бот MAX отправит его всем 5 участникам.",
      action: "Отправить",
    },
    cancel: {
      icon: "warning" as IconName,
      title: "Отменить игру?",
      copy: "Укажите причину. Все участники получат уведомление от бота.",
      action: "Отменить игру",
    },
  }[type];
  return (
    <div className="modal-layer">
      <div className="modal-backdrop" role="button" tabIndex={0} onClick={close} />
      <div className="sheet">
        <div className="sheet__handle" />
        <div className={`sheet__icon sheet__icon--${type}`}><Icon name={content.icon} size={25} /></div>
        <div className="sheet__title">{content.title}</div>
        <div className="sheet__copy">{content.copy}</div>
        {type === "join" && (
          <div className="check-row" role="checkbox" aria-checked={checked} tabIndex={0} onClick={() => setChecked(!checked)}>
            <div className={`checkbox${checked ? " is-checked" : ""}`}>{checked && <Icon name="check" size={15} />}</div>
            <div><strong>Возьму мяч</strong><span>Сообщим об этом другим игрокам</span></div>
          </div>
        )}
        {(type === "message" || type === "cancel") && (
          <div className="fake-input" role="textbox" contentEditable suppressContentEditableWarning>
            {type === "message" ? "Встречаемся у главного входа за 10 минут" : "Поле временно закрыто"}
          </div>
        )}
        <div className="sheet__buttons">
          <Button kind={type === "leave" || type === "cancel" ? "danger" : "primary"} onClick={confirm}>{content.action}</Button>
          {type !== "success" && <Button kind="ghost" onClick={close}>Не сейчас</Button>}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("onboarding");
  const [sheet, setSheet] = useState<Sheet>(null);
  const [selectedSlotId, setSelectedSlotId] = useState<number | null>(null);

  const navigate = (next: Screen) => {
    setScreen(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const openSlot = (id: number) => {
    setSelectedSlotId(id);
    navigate("details");
  };

  const hasNav = ["home", "my", "profile"].includes(screen);

  return (
    <div className="app-shell">
      <div className="phone">
        {screen === "onboarding" && <Onboarding start={() => navigate("home")} />}
        {screen === "home" && <Home open={openSlot} create={() => navigate("create")} />}
        {screen === "details" && selectedSlotId !== null && <Details slotId={selectedSlotId} back={() => navigate("home")} />}
        {screen === "create" && <CreateGame back={() => navigate("home")} publish={() => navigate("my")} />}
        {screen === "my" && <MyGames manage={() => navigate("manage")} />}
        {screen === "manage" && <Manage back={() => navigate("my")} message={() => setSheet("message")} cancel={() => setSheet("cancel")} />}
        {screen === "profile" && <Profile />}
        {hasNav && <BottomNav active={screen} navigate={navigate} />}
        {sheet && <Modal type={sheet} close={() => setSheet(null)} confirm={() => setSheet(null)} />}
      </div>
    </div>
  );
}
