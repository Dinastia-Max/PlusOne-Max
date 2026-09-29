import { getMaxUser, getUserName } from "../max";
import { Avatar, Button, Icon } from "../ui";

export default function Onboarding({ start }: { start: () => void }) {
  const user = getMaxUser();
  const name = getUserName(user);
  const firstName = user?.first_name || name;

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
        {user && (
          <div className="profile-preview">
            <Avatar name={name} tone="blue" large photoUrl={user.photo_url} />
            <div>
              <div className="profile-preview__hello">Привет, {firstName}!</div>
              <div className="profile-preview__source">
                <span className="verified"><Icon name="check" size={12} /></span>
                Профиль получен из MAX
              </div>
            </div>
          </div>
        )}
        <Button onClick={start}>Начать играть</Button>
      </div>
    </div>
  );
}
