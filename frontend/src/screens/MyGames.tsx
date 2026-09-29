import { fetchMySlots } from "../api";
import { hasEnded } from "../slotData";
import { useRequest } from "../useRequest";
import { Button, EmptyState, ErrorState, SlotCard, SlotCardSkeleton, TopBar } from "../ui";

export default function MyGames({
  open,
  manage,
  findGames,
}: {
  open: (id: number) => void;
  manage: (id: number) => void;
  findGames: () => void;
}) {
  const [state, retry] = useRequest(fetchMySlots, []);

  const upcoming = state.status === "success" ? state.data.filter((slot) => !hasEnded(slot)) : [];
  const joined = upcoming.filter((slot) => slot.role === "participant");
  const hosted = upcoming.filter((slot) => slot.role === "host");

  return (
    <div className="screen">
      <TopBar title="Мои игры" />
      {state.status === "loading" && (
        <div className="cards" role="status" aria-busy="true" aria-label="Загрузка ваших игр">
          <SlotCardSkeleton />
          <SlotCardSkeleton />
        </div>
      )}
      {state.status === "error" && <ErrorState error={state.error} retry={retry} />}
      {state.status === "success" && upcoming.length === 0 && (
        <EmptyState
          title="У вас пока нет игр"
          copy="Запишитесь на игру рядом или создайте свою — она появится здесь."
          action="Найти игру"
          onAction={findGames}
        />
      )}
      {state.status === "success" && upcoming.length > 0 && (
        <>
          <div className="my-summary">
            <div><strong>{upcoming.length}</strong><span>впереди</span></div>
            <div><strong>{hosted.length}</strong><span>создано вами</span></div>
          </div>
          <div className="section-heading"><div>Ближайшие</div></div>
          <div className="cards">
            {joined.length > 0 && <div className="role-label"><span className="role-dot" /> ВЫ УЧАСТВУЕТЕ</div>}
            {joined.map((slot) => (
              <SlotCard key={slot.id} slot={slot} role={slot.role} onOpen={() => open(slot.id)} />
            ))}
            {hosted.length > 0 && <div className="role-label role-label--host"><span className="role-dot" /> ВЫ ОРГАНИЗАТОР</div>}
            {hosted.map((slot) => (
              <SlotCard key={slot.id} slot={slot} role={slot.role} onOpen={() => open(slot.id)}>
                <div className="slot-card__action" onClick={(event) => event.stopPropagation()}>
                  <Button kind="secondary" onClick={() => manage(slot.id)}>Управлять игрой</Button>
                </div>
              </SlotCard>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
