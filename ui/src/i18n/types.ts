import type { Channel, Phase } from "../state/types";

export type Lang = "zh" | "en";

/**
 * Every user-visible string the UI owns. The Chinese and English
 * dictionaries share this shape; `copy.test.ts` fails if they drift apart.
 */
export interface Copy {
  meta: { title: string };
  face: { aria: (mood: string) => string };
  language: {
    group: string;
    zh: string;
    en: string;
  };
  phases: Record<Phase, string>;
  idle: {
    title: string;
    footer: string;
    tasks: string;
    focus: string;
    plan: string;
  };
  listening: { eyebrow: string; footer: string };
  thinking: { footer: string };
  planReview: {
    eyebrow: string;
    title: string;
    empty: string;
    step: (index: number) => string;
    minutes: (minutes: number) => string;
    more: (count: number) => string;
    confirm: string;
    revise: string;
    footer: string;
  };
  executing: {
    footer: string;
    empty: string;
    finish: string;
    skip: string;
    stuck: string;
    extend: string;
    step: (index: number) => string;
    minutes: (minutes: number) => string;
    ringHint: string;
    currentStep: string;
  };
  celebrate: { title: string; footer: string };
  resting: { eyebrow: string; footer: string };
  settings: {
    eyebrow: string;
    title: string;
    tokens: { title: string; detail: string }[];
    footer: string;
  };
  channel: {
    kicker: string;
    back: string;
    phoneBack: string;
    footerHint: string;
    emptyTasks: string;
    emptyPlans: string;
    focusRunning: string;
    focusPaused: string;
    focusReady: string;
    phonePurpose: Record<string, string>;
    phoneOverdue: string;
    phoneInUse: string;
    /** Unit shown next to the large reminder count. */
    reminderUnit: (count: number) => string;
    musicPlaying: string;
    musicPaused: string;
    musicFallback: string;
    unnamed: string;
    more: (count: number) => string;
    labels: Record<Channel, string>;
  };
  phoneBadge: {
    dockedCharging: string;
    docked: string;
    away: string;
  };
  companion: {
    max: string;
    streak: (days: number) => string;
  };
  offline: {
    base: string;
    reconnecting: string;
  };
  toast: {
    tasks: (count: number) => string;
    reminder: string;
    error: string;
  };
}
