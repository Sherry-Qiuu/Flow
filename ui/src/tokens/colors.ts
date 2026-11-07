export const colors = {
  bg: "#12100e",
  surface: "#1c1713",
  surfaceRaised: "#251e18",
  text: "#f4ecdf",
  muted: "#9d8f7f",
  amber: "#f0a35e",
  amberSoft: "#c47d43",
  sage: "#9bc7a8",
  rose: "#df9d9d",
  line: "rgba(244, 236, 223, 0.12)",
  glow: "rgba(240, 163, 94, 0.18)",
} as const;

export type FlowColor = keyof typeof colors;
