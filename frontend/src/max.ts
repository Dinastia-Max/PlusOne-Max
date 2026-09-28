export type MaxUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string | null;
  photo_url?: string | null;
};

type WebAppBridge = {
  initData?: string;
  initDataUnsafe?: { user?: MaxUser };
  ready?: () => void;
};

function getWebApp(): WebAppBridge | undefined {
  return (window as unknown as { WebApp?: WebAppBridge }).WebApp;
}

export function getInitData(): string {
  return getWebApp()?.initData ?? "";
}

export function isAuthorized(): boolean {
  return getInitData() !== "";
}

export function getMaxUser(): MaxUser | null {
  const user = getWebApp()?.initDataUnsafe?.user;
  return user && typeof user.id === "number" ? user : null;
}

export function getUserName(user: MaxUser | null): string {
  if (!user) return "";
  const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ");
  return fullName || user.username || "";
}

export function signalReady(): void {
  getWebApp()?.ready?.();
}
