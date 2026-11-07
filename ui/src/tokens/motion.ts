import type { Transition } from "framer-motion";

export const durations = {
  quick: 0.2,
  normal: 0.4,
  slow: 0.8,
} as const;

export const transitions = {
  quick: { duration: durations.quick, ease: "easeOut" },
  normal: { duration: durations.normal, ease: "easeOut" },
  slow: { duration: durations.slow, ease: "easeInOut" },
  spring: { type: "spring", stiffness: 120, damping: 18 },
} as const satisfies Record<string, Transition>;
