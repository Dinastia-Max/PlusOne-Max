import { useState } from "react";
import CreateGame from "./screens/CreateGame";
import Details from "./screens/Details";
import Home from "./screens/Home";
import Manage from "./screens/Manage";
import MyGames from "./screens/MyGames";
import Onboarding from "./screens/Onboarding";
import Profile from "./screens/Profile";
import { BottomNav, type Screen } from "./ui";

const ONBOARDING_KEY = "plusone.onboarded";

function wasOnboarded(): boolean {
  try {
    return window.localStorage.getItem(ONBOARDING_KEY) === "1";
  } catch {
    return false;
  }
}

function markOnboarded(): void {
  try {
    window.localStorage.setItem(ONBOARDING_KEY, "1");
  } catch {
    // Storage can be unavailable in restricted webviews; onboarding will just show again.
  }
}

export default function App() {
  const [screen, setScreen] = useState<Screen>(() => (wasOnboarded() ? "home" : "onboarding"));
  const [slotId, setSlotId] = useState<number | null>(null);
  const [detailsFrom, setDetailsFrom] = useState<"home" | "my">("home");
  const [manageFrom, setManageFrom] = useState<"details" | "my">("my");

  const navigate = (next: Screen) => {
    setScreen(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const openSlot = (id: number, from: "home" | "my") => {
    setSlotId(id);
    setDetailsFrom(from);
    navigate("details");
  };

  const openManage = (id: number, from: "details" | "my") => {
    setSlotId(id);
    setManageFrom(from);
    navigate("manage");
  };

  const hasNav = ["home", "my", "profile"].includes(screen);

  return (
    <div className="app-shell">
      <div className="phone">
        {screen === "onboarding" && (
          <Onboarding
            start={() => {
              markOnboarded();
              navigate("home");
            }}
          />
        )}
        {screen === "home" && <Home open={(id) => openSlot(id, "home")} create={() => navigate("create")} />}
        {screen === "details" && slotId !== null && (
          <Details
            slotId={slotId}
            back={() => navigate(detailsFrom)}
            manage={() => openManage(slotId, "details")}
          />
        )}
        {screen === "create" && <CreateGame back={() => navigate("home")} created={() => navigate("my")} />}
        {screen === "my" && (
          <MyGames
            open={(id) => openSlot(id, "my")}
            manage={(id) => openManage(id, "my")}
            findGames={() => navigate("home")}
          />
        )}
        {screen === "manage" && slotId !== null && (
          <Manage slotId={slotId} back={() => navigate(manageFrom)} canceled={() => navigate("my")} />
        )}
        {screen === "profile" && <Profile />}
        {hasNav && <BottomNav active={screen} navigate={navigate} />}
      </div>
    </div>
  );
}
