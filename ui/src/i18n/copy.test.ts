import { describe, expect, it } from "vitest";
import {
  COPY,
  formatClock,
  formatDate,
  formatIsoDate,
  parseLang,
} from "./index";
import { SERVER_COPY_KEYS, translateServerText } from "./server";

const at = new Date(2026, 10, 7, 19, 0, 0);

function shape(value: unknown): unknown {
  if (typeof value === "function") {
    return "fn";
  }
  if (Array.isArray(value)) {
    return value.map(shape);
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [
          key,
          shape((value as Record<string, unknown>)[key]),
        ]),
    );
  }
  return typeof value;
}

describe("i18n copy", () => {
  it("keeps the Chinese and English dictionaries in sync", () => {
    expect(shape(COPY.en)).toEqual(shape(COPY.zh));
  });

  it("has no blank copy", () => {
    const walk = (value: unknown, path: string): void => {
      if (typeof value === "string") {
        expect(value.trim(), path).not.toBe("");
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((entry, index) => walk(entry, `${path}[${index}]`));
        return;
      }
      if (value !== null && typeof value === "object") {
        Object.entries(value).forEach(([key, entry]) =>
          walk(entry, `${path}.${key}`),
        );
      }
    };
    walk(COPY.zh, "zh");
    walk(COPY.en, "en");
  });

  it("formats the clock and dates per language", () => {
    expect(formatClock(at)).toBe("19:00");
    expect(formatDate(at, "zh")).toContain("11月7日");
    expect(formatDate(at, "en")).toContain("Nov 7");
    expect(formatIsoDate("2026-11-07", "en")).toBe("Nov 7");
    expect(formatIsoDate("周五", "en")).toBe("周五");
  });

  it("parses explicit language overrides only", () => {
    expect(parseLang("en")).toBe("en");
    expect(parseLang("zh")).toBe("zh");
    expect(parseLang("fr")).toBeNull();
    expect(parseLang(null)).toBeNull();
  });
});

describe("backend chrome translation", () => {
  it("translates known chrome and passes content through", () => {
    expect(translateServerText("专注计时", "en")).toBe("Focus timer");
    expect(translateServerText("专注计时", "zh")).toBe("专注计时");
    expect(translateServerText("写引言", "en")).toBe("写引言");
    expect(translateServerText(null, "en")).toBe("");
  });

  it("maps every registered key to a different English string", () => {
    expect(SERVER_COPY_KEYS.length).toBeGreaterThan(20);
    for (const key of SERVER_COPY_KEYS) {
      const translated = translateServerText(key, "en");
      expect(translated, key).not.toBe(key);
      expect(translated.trim(), key).not.toBe("");
    }
  });
});
