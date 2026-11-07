import { PageShell, type PageProps } from "../components/PageShell";

const TOKENS = [
  ["暖色低饱和", "琥珀 / 鼠尾草 / 玫瑰"],
  ["字号阶梯", "正文 30 · 步骤 48 · 时钟 92"],
  ["动效", "200 / 400 / 800 ms，只用 transform + opacity"],
  ["无触屏", "所有操作都有语音或手势等效路径"],
];

export function Settings({ state }: PageProps) {
  return (
    <PageShell
      className="settings"
      footer="设置由语音或手势打开"
    >
      <p className="eyebrow">设计系统</p>
      <h1 className="page__title">少一点，但更清楚</h1>
      <div className="settings__tokens">
        {TOKENS.map(([title, detail]) => (
          <div className="settings__token" key={title}>
            <span>{title}</span>
            <small>{detail}</small>
          </div>
        ))}
      </div>
      <p className="page__message">{state.message}</p>
    </PageShell>
  );
}
