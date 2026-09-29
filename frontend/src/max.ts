import { useEffect, useRef } from "react";

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
  BackButton?: {
    show?: () => void;
    hide?: () => void;
    onClick?: (callback: () => void) => void;
    offClick?: (callback: () => void) => void;
  };
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

export function useBackButton(onBack: (() => void) | null): void {
  const handlerRef = useRef(onBack);
  useEffect(() => {
    handlerRef.current = onBack;
  });

  const enabled = onBack !== null;
  useEffect(() => {
    const button = getWebApp()?.BackButton;
    if (!enabled || !button) return;

    const callback = () => handlerRef.current?.();
    button.onClick?.(callback);
    button.show?.();
    return () => {
      button.offClick?.(callback);
      button.hide?.();
    };
  }, [enabled]);
}
