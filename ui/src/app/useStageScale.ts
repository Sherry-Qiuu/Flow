import { useEffect, useState } from "react";

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
  return Math.min(width / 720, height / 720);
}
