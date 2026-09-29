import { useState } from "react";
import { ApiError, fetchHostContact, joinSlot, leaveSlot } from "../api";
import {
  formatDate,
  formatDayLabel,
  formatDayOfMonth,
  formatFreeSeats,
  formatMonthShort,
  formatTimeRange,
} from "../format";
import { isMaxLink, openMaxLink } from "../max";
import { hasEnded, hasStarted, isFull, slotStatus, useSlotBundle, type SlotBundle } from "../slotData";
import { Button, ConfirmSheet, ErrorState, InfoRow, ProgressRing, TopBar } from "../ui";
import { useRequest } from "../useRequest";

type Sheet = "join" | "leave" | "joined" | null;

function ContactAction({ slotId }: { slotId: number }) {
  const [state] = useRequest((signal) => fetchHostContact(slotId, signal), [slotId]);
  if (state.status !== "success") return null;
  const { type, href } = state.data;
  if (type === "none" || !href) return null;
  if (type === "max") {
    if (!isMaxLink(href)) return null;
    return (
      <Button kind="secondary" onClick={() => openMaxLink(href)}>
        Связаться с организатором
      </Button>
    );
  }
  if (!href.startsWith("tel:")) return null;
  return (
    <a className="button button--secondary" href={href}>
      Связаться с организатором
    </a>
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

function SlotContent({ bundle, isHost, joined }: { bundle: SlotBundle; isHost: boolean; joined: boolean }) {
  const { slot } = bundle;
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
          {(isHost || joined) && (
            <>
              <div className="divider" />
              <InfoRow
                icon="profile"
                label="ВАША РОЛЬ"
                value={isHost ? "Вы организатор" : "Вы записаны на игру"}
              />
            </>
          )}
        </div>
      </div>
    </>
  );
}

export default function Details({
  slotId,
  back,
  manage,
}: {
  slotId: number;
  back: () => void;
  manage: () => void;
}) {
  const [state, reload] = useSlotBundle(slotId);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const bundle = state.status === "success" ? state.data : null;
  const isHost = bundle?.slot.is_host ?? false;
  const joined = bundle !== null && bundle.participants.some((participant) => participant.is_current_user);

  const openSheet = (next: Sheet) => {
    setActionError(null);
    setSheet(next);
  };

  const run = async (action: () => Promise<void>, done: Sheet) => {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      reload(true);
      setSheet(done);
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "Не удалось выполнить действие.");
      if (error instanceof ApiError && (error.kind === "conflict" || error.kind === "not_found")) reload(true);
    } finally {
      setBusy(false);
    }
  };

  const renderAction = () => {
    if (!bundle) return null;
    const { slot } = bundle;
    if (isHost) {
      return (
        <>
          <Button kind="secondary" onClick={manage}>Управлять игрой</Button>
          <div className="sticky-action__caption">Вы организатор этой игры</div>
        </>
      );
    }
    if (joined) {
      return hasStarted(slot) ? (
        <>
          <ContactAction slotId={slot.id} />
          <Button kind="secondary" disabled>Вы участвуете</Button>
          <div className="sticky-action__caption">Игра уже началась</div>
        </>
      ) : (
        <>
          <ContactAction slotId={slot.id} />
          <Button kind="secondary" onClick={() => openSheet("leave")}>Отказаться от участия</Button>
          <div className="sticky-action__caption">Ваше место сразу вернётся в набор</div>
        </>
      );
    }
    if (hasEnded(slot)) {
      return (
        <>
          <Button disabled>Игра завершена</Button>
          <div className="sticky-action__caption">Запись закрыта</div>
        </>
      );
    }
    if (hasStarted(slot)) {
      return (
        <>
          <Button disabled>Игра уже началась</Button>
          <div className="sticky-action__caption">Запись закрыта</div>
        </>
      );
    }
    if (isFull(slot)) {
      return (
        <>
          <Button disabled>Мест нет</Button>
          <div className="sticky-action__caption">Все места заняты</div>
        </>
      );
    }
    return (
      <>
        <Button onClick={() => openSheet("join")}>Записаться на игру</Button>
        <div className="sticky-action__caption">{formatFreeSeats(slot.max_players - slot.participants_count)}</div>
      </>
    );
  };

  const slot = bundle?.slot;
  const closeSheet = () => setSheet(null);

  return (
    <div className="screen detail-screen">
      <TopBar title="Игра" back={back} />
      {state.status === "loading" && <DetailsSkeleton />}
      {state.status === "error" && (
        <div className="detail-content">
          <ErrorState error={state.error} retry={reload} />
        </div>
      )}
      {bundle && (
        <>
          <SlotContent bundle={bundle} isHost={isHost} joined={joined} />
          <div className="sticky-action">{renderAction()}</div>
        </>
      )}
      {slot && sheet === "join" && (
        <ConfirmSheet
          tone="join"
          icon="ball"
          title="Записаться на игру?"
          copy={`${formatDayLabel(slot.start_at)}, ${formatTimeRange(slot.start_at, slot.end_at)} · ${slot.field.name}`}
          confirmLabel="Записаться"
          busy={busy}
          error={actionError}
          onConfirm={() => run(() => joinSlot(slot.id), "joined")}
          onClose={closeSheet}
        />
      )}
      {slot && sheet === "leave" && (
        <ConfirmSheet
          tone="leave"
          icon="warning"
          title="Точно отказаться?"
          copy={
            new Date(slot.start_at).getTime() - Date.now() < 2 * 3_600_000
              ? "До игры меньше 2 часов. Ваше место сразу вернётся в набор."
              : "Ваше место сразу вернётся в набор."
          }
          confirmLabel="Да, отказаться"
          danger
          busy={busy}
          error={actionError}
          onConfirm={() => run(() => leaveSlot(slot.id), null)}
          onClose={closeSheet}
        />
      )}
      {sheet === "joined" && (
        <ConfirmSheet
          tone="success"
          icon="check"
          title="Вы в игре!"
          copy="Место за вами закреплено. Игра появилась в разделе «Мои игры»."
          confirmLabel="Отлично"
          onConfirm={closeSheet}
          onClose={closeSheet}
          hideDismiss
        />
      )}
    </div>
  );
}
