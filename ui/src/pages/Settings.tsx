import { PageShell, type PageProps } from "../components/PageShell";
import { useI18n } from "../i18n";

export function Settings({ state }: PageProps) {
  const { t, srv } = useI18n();
  return (
    <PageShell className="settings" footer={t.settings.footer}>
      <p className="eyebrow">{t.settings.eyebrow}</p>
      <h1 className="page__title">{t.settings.title}</h1>
      <div className="settings__tokens">
        {t.settings.tokens.map((token) => (
          <div className="settings__token" key={token.title}>
            <span>{token.title}</span>
            <small>{token.detail}</small>
          </div>
        ))}
      </div>
      <p className="page__message">
        {srv(state.message) || t.phases.settings}
      </p>
    </PageShell>
  );
}
