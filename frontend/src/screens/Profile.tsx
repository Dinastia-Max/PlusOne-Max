import { fetchMySlots } from "../api";
import { getMaxUser, getUserName, isAuthorized } from "../max";
import { hasEnded } from "../slotData";
import { useRequest } from "../useRequest";
import { Avatar, Icon, SelectRow, TopBar } from "../ui";

export default function Profile() {
  const user = getMaxUser();
  const name = getUserName(user);
  const [state] = useRequest((signal) => (isAuthorized() ? fetchMySlots(signal) : Promise.resolve(null)), []);

  const stats = state.status === "success" && state.data ? state.data : null;
  const dash = state.status === "loading" ? "…" : "—";

  return (
    <div className="screen">
      <TopBar title="Профиль" />
      <div className="profile-hero">
        <Avatar name={name || "Гость"} tone="blue" large photoUrl={user?.photo_url} />
        <div className="page-title">{name || "Гость"}</div>
        {user ? (
          <div className="profile-source"><span className="verified"><Icon name="check" size={12} /></span> Профиль MAX</div>
        ) : (
          <div className="profile-source">Откройте приложение из MAX, чтобы увидеть профиль</div>
        )}
      </div>
      <div className="profile-stats">
        <div><strong>{stats ? stats.length : dash}</strong><span>игр</span></div>
        <div><strong>{stats ? stats.filter((slot) => slot.role === "host").length : dash}</strong><span>создано</span></div>
        <div><strong>{stats ? stats.filter((slot) => !hasEnded(slot)).length : dash}</strong><span>впереди</span></div>
      </div>
      {user && (
        <div className="form-section profile-section">
          <div className="form-label">ДАННЫЕ MAX</div>
          <div className="form-card">
            <SelectRow readOnly icon="profile" label="Имя" value={name || "—"} />
            {user.username && (
              <>
                <div className="divider" />
                <SelectRow readOnly icon="message" label="Никнейм" value={`@${user.username}`} />
              </>
            )}
          </div>
          <div className="privacy-note"><Icon name="shield" size={18} /><span>Мы берём только имя и фото из вашего профиля MAX</span></div>
        </div>
      )}
    </div>
  );
}
