import { useState } from "react";
import { ApiError, cancelSlot } from "../api";
import { formatDate, formatDateTime, formatDayLabel, formatTimeRange } from "../format";
import { getMaxUser } from "../max";
import { hasEnded, useSlotBundle } from "../slotData";
import { Avatar, Button, ConfirmSheet, ErrorState, Icon, TopBar } from "../ui";

const TONES = ["mint", "sky", "violet", "orange", "blue"];

export default function Manage({
  slotId,
  back,
  canceled,
}: {
  slotId: number;
  back: () => void;
  canceled: () => void;
}) {
  const [state, reload] = useSlotBundle(slotId);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const me = getMaxUser();

  const cancel = async () => {
    setBusy(true);
    setActionError(null);
    try {
      await cancelSlot(slotId);
      setConfirming(false);
      canceled();
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "Не удалось отменить игру.");
      setBusy(false);
    }
  };

  return (
    <div className="screen">
      <TopBar title="Управление игрой" back={back} />
      {state.status === "loading" && (
        <div role="status" aria-busy="true" aria-label="Загрузка игры">
          <div className="skeleton" style={{ height: 120, borderRadius: 24 }} />
        </div>
      )}
      {state.status === "error" && <ErrorState error={state.error} retry={reload} />}
      {state.status === "success" && me?.id !== state.data.slot.host_id && (
        <div className="state-card">
          <div className="state-card__icon state-card__icon--danger"><Icon name="warning" size={25} /></div>
          <div className="state-card__title">Только для организатора</div>
          <div className="state-card__copy">Управлять игрой может тот, кто её создал.</div>
          <Button kind="secondary" onClick={back}>Назад</Button>
        </div>
      )}
      {state.status === "success" && me?.id === state.data.slot.host_id && (() => {
        const { slot, participants } = state.data;
        const ended = hasEnded(slot);
        return (
          <>
            <div className="manage-hero">
              <div className="eyebrow eyebrow--blue">{formatDayLabel(slot.start_at).toUpperCase()}, {formatDate(slot.start_at).toUpperCase()}</div>
              <div className="page-title">{formatTimeRange(slot.start_at, slot.end_at)}</div>
              <div className="location-caption"><Icon name="location" size={15} /> {slot.field.name}</div>
            </div>
            <div className="section-heading">
              <div>Состав</div>
              <span>{participants.length} из {slot.max_players}</span>
            </div>
            {participants.length === 0 ? (
              <div className="state-card">
                <div className="state-card__title">Пока никто не записался</div>
                <div className="state-card__copy">Участники появятся здесь, как только запишутся.</div>
              </div>
            ) : (
              <div className="people-list">
                {participants.map((participant, index) => (
                  <div className="person-row" key={participant.user_id}>
                    <Avatar name={String(index + 1)} tone={TONES[index % TONES.length]} />
                    <div>
                      <strong>Участник {index + 1}</strong>
                      <span>Записался {formatDateTime(participant.joined_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {!ended && (
              <div className="danger-zone">
                <Button kind="danger" onClick={() => { setActionError(null); setConfirming(true); }}>Отменить игру</Button>
                <span>Игра исчезнет из списка. Участникам придётся сообщить самостоятельно.</span>
              </div>
            )}
          </>
        );
      })()}
      {confirming && (
        <ConfirmSheet
          tone="cancel"
          icon="warning"
          title="Отменить игру?"
          copy="Игра пропадёт из списка, записавшиеся участники потеряют место. Действие нельзя отменить."
          confirmLabel="Отменить игру"
          danger
          busy={busy}
          error={actionError}
          onConfirm={cancel}
          onClose={() => setConfirming(false)}
        />
      )}
    </div>
  );
}
