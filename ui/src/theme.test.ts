import { describe, expect, it } from "vitest";
import theme from "./theme.css?raw";

describe("dark theme", () => {
  it("has the spec's colors", () => {
    for (const token of [
      "--app-bg: #1e1e1e",
      "--panel: #2b2b2b",
      "--canvas: #262626",
      "--paper: #f4f3ef",
      "--accent: #3b8eea",
      "--axis-x: #e2504c",
      "--axis-y: #5fa83a",
      "--pen-cross: #e0245e",
    ]) {
      expect(theme).toContain(token);
    }
  });
});
