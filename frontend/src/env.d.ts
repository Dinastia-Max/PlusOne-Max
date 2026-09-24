/// <reference types="vite/client" />

interface MaxWebApp {
  platform?: string;
  ready?: () => void;
  expand?: () => void;
}

interface Window {
  WebApp?: MaxWebApp;
}
