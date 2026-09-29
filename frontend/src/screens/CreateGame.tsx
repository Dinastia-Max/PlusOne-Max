import { useMemo, useState } from "react";
import { ApiError, createSlot, fetchFields, type Field } from "../api";
import { formatDate, formatDayLabel, formatDuration, localDateKey, localTimeValue } from "../format";
import { getMaxUser } from "../max";
import { useRequest } from "../useRequest";
import { Button, ErrorState, Icon, SelectRow, TopBar } from "../ui";

const DAYS_AHEAD = 7;
const DURATIONS = [60, 90, 120, 150, 180];
const MIN_PLAYERS_LIMIT = 2;
const MAX_PLAYERS_LIMIT = 30;

function upcomingDays(): Date[] {
  const today = new Date();
  return Array.from({ length: DAYS_AHEAD }, (_, index) => new Date(today.getFullYear(), today.getMonth(), today.getDate() + index));
}

function defaultStart(): Date {
  const start = new Date();
  start.setMinutes(0, 0, 0);
  start.setHours(start.getHours() + 1);
  if (localDateKey(start) !== localDateKey(new Date())) {
    start.setHours(19, 0, 0, 0);
  }
  return start;
}

function Counter({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
}) {
  const step = (delta: number) => onChange(Math.min(max, Math.max(min, value + delta)));
  return (
    <div className="counter-card">
      <span>{label}</span>
      <div>
        <b
          role="button"
          aria-label={`${label}: меньше`}
          tabIndex={0}
          className={value <= min ? "is-disabled" : ""}
          onClick={() => step(-1)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") step(-1);
          }}
        >
          −
        </b>
        <strong>{value}</strong>
        <b
          role="button"
          aria-label={`${label}: больше`}
          tabIndex={0}
          className={value >= max ? "is-disabled" : ""}
          onClick={() => step(1)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") step(1);
          }}
        >
          +
        </b>
      </div>
    </div>
  );
}

function Form({ fields, back, created }: { fields: Field[]; back: () => void; created: (slotId: number) => void }) {
  const days = useMemo(upcomingDays, []);
  const initialStart = useMemo(defaultStart, []);
  const [fieldId, setFieldId] = useState<number>(fields[0]?.id ?? 0);
  const [dayKey, setDayKey] = useState(localDateKey(initialStart));
  const [time, setTime] = useState(localTimeValue(initialStart));
  const [duration, setDuration] = useState(90);
  const [minPlayers, setMinPlayers] = useState(6);
  const [maxPlayers, setMaxPlayers] = useState(10);
  const [hasBall, setHasBall] = useState(true);
  const hasMaxUsername = Boolean(getMaxUser()?.username);
  const [contactType, setContactType] = useState<"max" | "phone" | "none">(hasMaxUsername ? "max" : "none");
  const [phone, setPhone] = useState("");
  const [phoneConsent, setPhoneConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const field = fields.find((item) => item.id === fieldId);
  const selectedDay = days.find((day) => localDateKey(day) === dayKey) ?? days[0];

  const changeMin = (value: number) => {
    setMinPlayers(value);
    if (maxPlayers < value) setMaxPlayers(value);
  };
  const changeMax = (value: number) => {
    setMaxPlayers(value);
    if (minPlayers > value) setMinPlayers(value);
  };

  const publish = async () => {
    if (busy) return;
    if (!field) {
      setError("Выберите площадку.");
      return;
    }
    if (contactType === "phone" && !/^\+[1-9]\d{7,14}$/.test(phone.replace(/[\s()-]/g, ""))) {
      setError("Укажите телефон в международном формате, например +79991234567.");
      return;
    }
    if (contactType === "phone" && !phoneConsent) {
      setError("Подтвердите согласие на показ телефона участникам.");
      return;
    }
    const start = new Date(`${dayKey}T${time}:00`);
    if (Number.isNaN(start.getTime())) {
      setError("Укажите время начала.");
      return;
    }
    if (start.getTime() <= Date.now()) {
      setError("Игра должна начинаться в будущем.");
      return;
    }
    const end = new Date(start.getTime() + duration * 60_000);

    setBusy(true);
    setError(null);
    try {
      const slot = await createSlot({
        field_id: field.id,
        start_at: start.toISOString(),
        end_at: end.toISOString(),
        min_players: minPlayers,
        max_players: maxPlayers,
        has_ball: hasBall,
        host_contact_type: contactType,
        host_phone: contactType === "phone" ? phone : null,
      });
      created(slot.id);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Не удалось опубликовать игру.");
      setBusy(false);
    }
  };

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
          <div className="form-card">
            <SelectRow icon="location" label="Поле" value={field?.name ?? "Выберите площадку"}>
              <select
                className="select-row__native"
                aria-label="Поле"
                value={fieldId}
                onChange={(event) => setFieldId(Number(event.target.value))}
              >
                {fields.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </SelectRow>
          </div>
          {field && <div className="form-hint">{field.address}</div>}
        </div>
        <div className="form-section">
          <div className="form-label">КОГДА</div>
          <div className="form-card">
            <SelectRow icon="calendar" label="Дата" value={`${formatDayLabel(selectedDay)}, ${formatDate(selectedDay)}`}>
              <select
                className="select-row__native"
                aria-label="Дата"
                value={dayKey}
                onChange={(event) => setDayKey(event.target.value)}
              >
                {days.map((day) => (
                  <option key={localDateKey(day)} value={localDateKey(day)}>
                    {formatDayLabel(day)}, {formatDate(day)}
                  </option>
                ))}
              </select>
            </SelectRow>
            <div className="divider" />
            <SelectRow icon="clock" label="Начало" value={time || "Укажите время"}>
              <input
                className="select-row__native"
                aria-label="Начало"
                type="time"
                value={time}
                onChange={(event) => setTime(event.target.value)}
              />
            </SelectRow>
            <div className="divider" />
            <SelectRow icon="clock" label="Длительность" value={formatDuration(duration)}>
              <select
                className="select-row__native"
                aria-label="Длительность"
                value={duration}
                onChange={(event) => setDuration(Number(event.target.value))}
              >
                {DURATIONS.map((minutes) => (
                  <option key={minutes} value={minutes}>{formatDuration(minutes)}</option>
                ))}
              </select>
            </SelectRow>
          </div>
        </div>
        <div className="form-section">
          <div className="form-label">КОМАНДА</div>
          <div className="counter-grid">
            <Counter label="Минимум" value={minPlayers} onChange={changeMin} min={MIN_PLAYERS_LIMIT} max={MAX_PLAYERS_LIMIT} />
            <Counter label="Максимум" value={maxPlayers} onChange={changeMax} min={MIN_PLAYERS_LIMIT} max={MAX_PLAYERS_LIMIT} />
          </div>
        </div>
        <div className="form-section">
          <div className="form-label">КОНТАКТ ОРГАНИЗАТОРА</div>
          <div className="form-card">
            <SelectRow
              icon="message"
              label="Как связаться"
              value={contactType === "max" ? "Профиль MAX" : contactType === "phone" ? "Телефон" : "Не указывать"}
            >
              <select
                className="select-row__native"
                aria-label="Контакт организатора"
                value={contactType}
                onChange={(event) => setContactType(event.target.value as "max" | "phone" | "none")}
              >
                <option value="max" disabled={!hasMaxUsername}>Профиль MAX</option>
                <option value="phone">Телефон</option>
                <option value="none">Не указывать</option>
              </select>
            </SelectRow>
            {contactType === "phone" && (
              <>
                <div className="divider" />
                <input
                  className="contact-input"
                  aria-label="Телефон организатора"
                  type="tel"
                  inputMode="tel"
                  placeholder="+7 999 123-45-67"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                />
              </>
            )}
          </div>
          <div className="form-hint">Контакт увидят только записавшиеся участники.</div>
          {!hasMaxUsername && (
            <div className="form-hint">
              Чтобы открыть чат в MAX, в профиле нужен username. Пока его нет — укажите телефон.
            </div>
          )}
          {contactType === "phone" && (
            <div
              className="check-row contact-consent"
              role="checkbox"
              aria-checked={phoneConsent}
              tabIndex={0}
              onClick={() => setPhoneConsent(!phoneConsent)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") setPhoneConsent(!phoneConsent);
              }}
            >
              <div className={`checkbox${phoneConsent ? " is-checked" : ""}`}>{phoneConsent && <Icon name="check" size={15} />}</div>
              <div><strong>Разрешаю показать мой телефон</strong><span>Только записавшимся на эту игру</span></div>
            </div>
          )}
        </div>
        <div
          className="form-card switch-card"
          role="switch"
          aria-checked={hasBall}
          tabIndex={0}
          onClick={() => setHasBall(!hasBall)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") setHasBall(!hasBall);
          }}
        >
          <div className="select-row__icon"><Icon name="ball" /></div>
          <div className="select-row__copy"><strong>У меня будет мяч</strong><span>Покажем это участникам</span></div>
          <div className={`toggle${hasBall ? " is-on" : ""}`}><div /></div>
        </div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <div className="form-submit">
          <Button onClick={publish} disabled={busy}>{busy ? "Публикуем…" : "Опубликовать игру"}</Button>
        </div>
      </div>
    </div>
  );
}

export default function CreateGame({ back, created }: { back: () => void; created: (slotId: number) => void }) {
  const [state, retry] = useRequest(fetchFields, []);

  if (state.status === "success" && state.data.length > 0) {
    return <Form fields={state.data} back={back} created={created} />;
  }

  return (
    <div className="screen create-screen">
      <TopBar title="Новая игра" back={back} />
      <div className="create-content">
        {state.status === "loading" && (
          <div role="status" aria-busy="true" aria-label="Загрузка площадок">
            <div className="skeleton skeleton--title" style={{ width: "60%" }} />
            <div className="skeleton" style={{ height: 66, borderRadius: 18, marginBottom: 14 }} />
            <div className="skeleton" style={{ height: 200, borderRadius: 18 }} />
          </div>
        )}
        {state.status === "error" && <ErrorState error={state.error} retry={retry} />}
        {state.status === "success" && (
          <div className="state-card">
            <div className="state-card__title">Нет доступных площадок</div>
            <div className="state-card__copy">Создать игру пока негде. Загляните позже.</div>
          </div>
        )}
      </div>
    </div>
  );
}
