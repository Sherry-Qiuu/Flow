import { useI18n } from "../i18n";

/**
 * Two-segment language switch. It lives in the page footer so it is on
 * screen at every phase without competing with the clock and badges that
 * occupy the top corners.
 */
export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div
      className="language-switch"
      role="group"
      aria-label={t.language.group}
    >
      <button
        type="button"
        className="language-switch__option"
        aria-pressed={lang === "zh"}
        onClick={() => setLang("zh")}
      >
        {t.language.zh}
      </button>
      <button
        type="button"
        className="language-switch__option"
        aria-pressed={lang === "en"}
        onClick={() => setLang("en")}
      >
        {t.language.en}
      </button>
    </div>
  );
}
