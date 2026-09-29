import type { CSSProperties, ReactNode } from "react";
import type { ApiError, SlotListItem } from "./api";
import { formatDate, formatDayLabel, formatFreeSeats, formatTimeRange } from "./format";

export type Screen = "onboarding" | "home" | "details" | "create" | "my" | "profile" | "manage";

export type IconName =
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

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
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

export function Button({
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
      aria-disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onClick={disabled ? undefined : onClick}
      onKeyDown={(event) => {
        if (!disabled && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onClick?.();
        }
      }}
    >
      {icon && <Icon name={icon} size={19} />}
      <span>{children}</span>
    </div>
  );
}

export function Avatar({
  name,
  tone = "blue",
  large = false,
  photoUrl,
}: {
  name: string;
  tone?: string;
  large?: boolean;
  photoUrl?: string | null;
}) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <div className={`avatar avatar--${tone}${large ? " avatar--large" : ""}`}>
      {photoUrl ? <img src={photoUrl} alt="" referrerPolicy="no-referrer" /> : initials || "?"}
    </div>
  );
}

export function TopBar({ title, back, action }: { title: string; back?: () => void; action?: ReactNode }) {
  return (
    <div className="topbar">
      <div className="topbar__side">
        {back && (
          <div
            className="icon-button"
            role="button"
            aria-label="Назад"
            tabIndex={0}
            onClick={back}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") back();
            }}
          >
            <Icon name="back" />
          </div>
        )}
      </div>
      <div className="topbar__title">{title}</div>
      <div className="topbar__side topbar__side--end">{action}</div>
    </div>
  );
}

export function BottomNav({ active, navigate }: { active: Screen; navigate: (screen: Screen) => void }) {
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
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") navigate(item.screen);
          }}
          key={item.screen}
        >
          <Icon name={item.icon} size={22} />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export function ProgressRing({ value, max }: { value: number; max: number }) {
  const share = max > 0 ? Math.min(value / max, 1) : 0;
  return (
    <div className="progress-ring" style={{ "--progress": `${share * 360}deg` } as CSSProperties}>
      <div>{value}</div>
      <span>из {max}</span>
    </div>
  );
}

export function InfoRow({ icon, label, value, sub }: { icon: IconName; label: string; value: string; sub?: string }) {
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

export function SelectRow({
  label,
  value,
  icon,
  children,
  readOnly = false,
}: {
  label: string;
  value: string;
  icon: IconName;
  children?: ReactNode;
  readOnly?: boolean;
}) {
  return (
    <div className={`select-row${readOnly ? " select-row--static" : ""}`}>
      <div className="select-row__icon"><Icon name={icon} /></div>
      <div className="select-row__copy"><span>{label}</span><strong>{value}</strong></div>
      {!readOnly && <Icon name="chevron" size={18} />}
      {children}
    </div>
  );
}

export function SlotCard({
  slot,
  role,
  onOpen,
  children,
}: {
  slot: SlotListItem;
  role?: "host" | "participant";
  onOpen: () => void;
  children?: ReactNode;
}) {
  const tone = FIELD_TONES[slot.field.id % FIELD_TONES.length];
  return (
    <div
      className="slot-card"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
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
          {role === "participant" && <div className="tag tag--success">Вы в игре</div>}
          {role === "host" && <div className="tag tag--host">Вы организатор</div>}
        </div>
      </div>
      {children}
    </div>
  );
}

export function SlotCardSkeleton() {
  return (
    <div className="slot-card slot-card--skeleton" aria-hidden="true">
      <div className="skeleton skeleton--line" style={{ width: "35%" }} />
      <div className="skeleton skeleton--title" style={{ width: "55%" }} />
      <div className="skeleton skeleton--line" style={{ width: "80%", marginTop: 22 }} />
      <div className="skeleton skeleton--line" style={{ width: "50%" }} />
    </div>
  );
}

function errorTexts(error: ApiError): { title: string; copy: string } {
  if (error.kind === "network") {
    return { title: "Сервер недоступен", copy: "Проверьте подключение к интернету и попробуйте ещё раз." };
  }
  if (error.kind === "unauthorized") {
    return { title: "Нужен вход через MAX", copy: error.message };
  }
  if (error.kind === "not_found") {
    return { title: "Не найдено", copy: error.message };
  }
  return { title: "Не удалось загрузить данные", copy: `${error.message} Попробуйте ещё раз чуть позже.` };
}

export function ErrorState({ error, retry }: { error: ApiError; retry: () => void }) {
  const { title, copy } = errorTexts(error);
  return (
    <div className="state-card" role="alert">
      <div className="state-card__icon state-card__icon--danger"><Icon name="warning" size={25} /></div>
      <div className="state-card__title">{title}</div>
      <div className="state-card__copy">{copy}</div>
      <Button kind="secondary" onClick={retry}>Повторить</Button>
    </div>
  );
}

export function EmptyState({
  title,
  copy,
  action,
  onAction,
}: {
  title: string;
  copy: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="state-card">
      <div className="state-card__icon"><Icon name="ball" size={25} /></div>
      <div className="state-card__title">{title}</div>
      <div className="state-card__copy">{copy}</div>
      {action && onAction && <Button kind="secondary" onClick={onAction}>{action}</Button>}
    </div>
  );
}

export type SheetTone = "join" | "leave" | "success" | "cancel";

export function ConfirmSheet({
  tone,
  icon,
  title,
  copy,
  confirmLabel,
  danger = false,
  busy = false,
  error,
  onConfirm,
  onClose,
  hideDismiss = false,
}: {
  tone: SheetTone;
  icon: IconName;
  title: string;
  copy: string;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onClose: () => void;
  hideDismiss?: boolean;
}) {
  return (
    <div className="modal-layer">
      <div className="modal-backdrop" role="button" tabIndex={-1} onClick={busy ? undefined : onClose} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="sheet__handle" />
        <div className={`sheet__icon sheet__icon--${tone}`}><Icon name={icon} size={25} /></div>
        <div className="sheet__title">{title}</div>
        <div className="sheet__copy">{copy}</div>
        {error && <div className="sheet__error" role="alert">{error}</div>}
        <div className="sheet__buttons">
          <Button kind={danger ? "danger" : "primary"} onClick={onConfirm} disabled={busy}>
            {busy ? "Подождите…" : confirmLabel}
          </Button>
          {!hideDismiss && <Button kind="ghost" onClick={onClose} disabled={busy}>Не сейчас</Button>}
        </div>
      </div>
    </div>
  );
}
