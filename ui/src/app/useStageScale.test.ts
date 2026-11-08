import { describe, expect, it } from "vitest";
import {
  computeScale,
  STAGE_HEIGHT,
  STAGE_WIDTH,
} from "./useStageScale";

describe("stage scale", () => {
  it("uses the 7\" 1024×600 panel as the design canvas", () => {
    expect(STAGE_WIDTH).toBe(1024);
    expect(STAGE_HEIGHT).toBe(600);
  });

  it("scales the canvas to the window without cropping", () => {
    expect(computeScale(1024, 600)).toBeCloseTo(1);
    expect(computeScale(2048, 1200)).toBeCloseTo(2);
    expect(computeScale(1024, 768)).toBeCloseTo(1);
    expect(computeScale(800, 480)).toBeCloseTo(800 / 1024);
  });
});
