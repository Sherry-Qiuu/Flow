import { useEffect, useState } from "react";

/** The panel on the device is a 7" 1024×600 TTL screen. */
export const STAGE_WIDTH = 1024;
export const STAGE_HEIGHT = 600;

export function useStageScale(): number {
  const [scale, setScale] = useState(() => computeScale());

  useEffect(() => {
    const update = () => setScale(computeScale());
    update();
    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", update);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("orientationchange", update);
    };
  }, []);

  return scale;
}

export function computeScale(
  width = window.innerWidth,
  height = window.innerHeight,
): number {
  return Math.min(width / STAGE_WIDTH, height / STAGE_HEIGHT);
}
