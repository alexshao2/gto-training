// Minimal Telegram WebApp SDK helper. Falls back gracefully if loaded outside Telegram.

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        expand: () => void;
        themeParams: Record<string, string>;
        colorScheme: "light" | "dark";
        initData: string;
        initDataUnsafe: {
          user?: {
            id: number;
            first_name?: string;
            last_name?: string;
            username?: string;
          };
        };
        HapticFeedback?: {
          impactOccurred: (style: "light" | "medium" | "heavy") => void;
          notificationOccurred: (type: "error" | "success" | "warning") => void;
        };
        MainButton?: {
          show: () => void;
          hide: () => void;
          setText: (t: string) => void;
          onClick: (cb: () => void) => void;
        };
      };
    };
  }
}

export function initTelegram() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    if (tg.colorScheme === "light") {
      document.documentElement.classList.add("tg-light");
    }
  } catch {
    // ignore
  }
}

export function hapticImpact(style: "light" | "medium" | "heavy" = "light") {
  window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(style);
}

export function hapticNotify(type: "error" | "success" | "warning") {
  window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred(type);
}

export function getTelegramUser() {
  return window.Telegram?.WebApp?.initDataUnsafe?.user;
}
