import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { FaceExpression } from "../components/FaceExpression";
import { PageShell } from "../components/PageShell";
import { makeInitialState } from "../state/reducer";
import type { FlowState, FaceMood } from "../state/types";
import { Celebrate } from "../pages/Celebrate";
import { Executing } from "../pages/Executing";
import { Idle } from "../pages/Idle";
import { Listening } from "../pages/Listening";
import { PlanReview } from "../pages/PlanReview";
import { Resting } from "../pages/Resting";
import { Settings } from "../pages/Settings";
import { Thinking } from "../pages/Thinking";
import { ChannelView } from "../pages/ChannelView";

const at = new Date("2026-11-07T19:00:00+08:00");

function state(overrides: Partial<FlowState> = {}): FlowState {
  return { ...makeInitialState(at), ...overrides };
}

describe("T05 pages", () => {
  it("renders every page without a clickable control", () => {
    const pages = [
      { component: Idle, state: state() },
      { component: Listening, state: state({ phase: "listening" }) },
      { component: Thinking, state: state({ phase: "thinking" }) },
      {
        component: PlanReview,
        state: state({
          phase: "plan_review",
          plan: {
            plan_id: "p_1",
            items: [
              { title: "列出 3 个论点", start: "19:00", est_minutes: 20 },
              { title: "写引言", start: "19:20", est_minutes: 30 },
            ],
          },
        }),
      },
      { component: Executing, state: state({ phase: "executing" }) },
      { component: Celebrate, state: state({ phase: "celebrating" }) },
      { component: Resting, state: state({ phase: "resting" }) },
      { component: Settings, state: state({ phase: "settings" }) },
    ];
    for (const page of pages) {
      const Page = page.component;
      const html = renderToStaticMarkup(<Page state={page.state} />);
      expect(html.length).toBeGreaterThan(80);
      expect(html).not.toMatch(/<a\s|<input|<select/);
    }
  });

  it("idle exposes large touch actions", () => {
    const html = renderToStaticMarkup(<Idle state={state()} />);
    expect(html).toContain("任务");
    expect(html).toContain("专注 15 分钟");
    expect(html).toContain("安排今天");
    expect(html).toMatch(/<button/);
  });

  it("keeps long Chinese step titles inside the executing page", () => {
    const html = renderToStaticMarkup(
      <Executing
        state={state({
          phase: "executing",
          step: {
            title:
              "打开课程论文文档，列出三个核心论点，并为每个论点找两条证据",
            detail: "只做这一小步",
            minutes: 20,
            remainingMs: 300000,
            totalMs: 1200000,
            index: 0,
            total: 3,
          },
        })}
      />,
    );
    expect(html).toContain("打开课程论文文档");
    expect(html).toContain("05:00");
    expect(html).not.toContain("任务列表");
  });

  it("renders all eight face moods", () => {
    const moods: FaceMood[] = [
      "neutral",
      "happy",
      "listening",
      "thinking",
      "sleepy",
      "excited",
      "concerned",
      "resting",
    ];
    for (const mood of moods) {
      const html = renderToStaticMarkup(
        <FaceExpression mood={mood} />,
      );
      expect(html).toContain("Flow 表情");
    }
  });

  it("shows the companion stage on idle", () => {
    const html = renderToStaticMarkup(
      <Idle
        state={state({
          companion: {
            exp: 12,
            level: 1,
            stage: "小苗",
            streak: 3,
            next_exp: 30,
          },
        })}
      />,
    );
    expect(html).toContain("小苗");
    expect(html).toContain("Lv.1");
  });

  it("shows the phone stand badge on idle", () => {
    const html = renderToStaticMarkup(
      <Idle
        state={state({
          phone: { present: true, charging: true },
        })}
      />,
    );
    expect(html).toContain("手机在架 · 充电中");
  });

  it("renders the active T04 channel without clickable controls", () => {
    const html = renderToStaticMarkup(
      <ChannelView
        state={state({
          phase: "idle",
          channel: "focus",
          channelActive: true,
          channelTitle: "专注计时",
          channelData: {
            remaining_seconds: 300,
            status: "running",
            running: true,
          },
          channelHints: ["说“暂停”", "说“返回”"],
        })}
      />,
    );
    expect(html).toContain("专注计时");
    expect(html).toContain("05:00");
    expect(html).toContain("正在专注");
    expect(html).toContain("返回");
    expect(html).toMatch(/<button/);
  });

  it("renders a task channel list", () => {
    const html = renderToStaticMarkup(
      <ChannelView
        state={state({
          phase: "idle",
          channel: "tasks",
          channelActive: true,
          channelTitle: "任务清单",
          channelData: {
            count: 2,
            items: [{ title: "写引言" }, { title: "列论点" }],
          },
          channelHints: ["说“完成第一条”"],
        })}
      />,
    );
    expect(html).toContain("任务清单");
    expect(html).toContain("写引言");
    expect(html).toContain("列论点");
  });

  it("page shell exposes a footer without interactive controls", () => {
    const html = renderToStaticMarkup(
      <PageShell footer="说“开始”">
        <p>内容</p>
      </PageShell>,
    );
    expect(html).toContain("说“开始”");
    expect(html).not.toMatch(/<button|<a\s/);
  });
});
