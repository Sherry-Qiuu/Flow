import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { translateServerText } from "./server";
import { EN } from "./en";
import { ZH } from "./zh";
import type { Copy, Lang } from "./types";

export const LANG_STORAGE_KEY = "flow.lang";

export const COPY: Record<Lang, Copy> = { zh: ZH, en: EN };

export function copyFor(lang: Lang): Copy {
  return COPY[lang];
}

export function localeFor(lang: Lang): string {
  return lang === "zh" ? "zh-CN" : "en-US";
}

export function parseLang(value: string | null | undefined): Lang | null {
  return value === "zh" || value === "en" ? value : null;
}

function readStoredLang(): Lang | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return parseLang(window.localStorage.getItem(LANG_STORAGE_KEY));
  } catch {
    return null;
  }
}

/**
 * Language precedence: `?lang=` for a quick demo override, then the last
 * choice stored on the device, then Chinese, the product's first language.
 */
export function detectLang(): Lang {
  if (typeof window === "undefined") {
    return "zh";
  }
  const fromQuery = parseLang(
    new URLSearchParams(window.location.search).get("lang"),
  );
  if (fromQuery !== null) {
    return fromQuery;
  }
  return readStoredLang() ?? "zh";
}

const clockFormat = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const dateFormats: Record<Lang, Intl.DateTimeFormat> = {
  zh: new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }),
  en: new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
  }),
};

const shortDateFormats: Record<Lang, Intl.DateTimeFormat> = {
  zh: new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
  }),
  en: new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }),
};

/** 24-hour clock; identical in both languages, so no language argument. */
export function formatClock(date: Date): string {
  return clockFormat.format(date);
}

export function formatDate(date: Date, lang: Lang): string {
  return dateFormats[lang].format(date);
}

/** Format a backend `YYYY-MM-DD` value; other strings pass through. */
export function formatIsoDate(iso: string, lang: Lang): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (match === null) {
    return iso;
  }
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return shortDateFormats[lang].format(date);
}

export interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Copy;
  /** Translate backend chrome; content passes through unchanged. */
  srv: (text: string | null | undefined) => string;
  formatClock: (date: Date) => string;
  formatDate: (date: Date) => string;
  formatIsoDate: (iso: string) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  children,
  initialLang,
}: {
  children: ReactNode;
  initialLang?: Lang;
}) {
  const [lang, setLangState] = useState<Lang>(
    () => initialLang ?? detectLang(),
  );

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(LANG_STORAGE_KEY, next);
      } catch {
        // A kiosk profile with storage disabled still switches this session.
      }
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = localeFor(lang);
    document.title = copyFor(lang).meta.title;
  }, [lang]);

  const value = useMemo<I18nValue>(() => {
    const t = copyFor(lang);
    return {
      lang,
      setLang,
      t,
      srv: (text) => translateServerText(text, lang),
      formatClock,
      formatDate: (date) => formatDate(date, lang),
      formatIsoDate: (iso) => formatIsoDate(iso, lang),
    };
  }, [lang, setLang]);

  return (
    <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
  );
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (value === null) {
    throw new Error("useI18n must be called inside I18nProvider");
  }
  return value;
}

export type { Copy, Lang };
