import { beforeEach, describe, expect, it } from "vitest";
import { getCompletedModuleIds, setModuleCompletion } from "../lib/progress";

describe("lesson completion progress", () => {
  beforeEach(() => localStorage.clear());

  it("adds and removes a completed lesson", () => {
    setModuleCompletion("track-1", "lesson-1", true);
    expect(getCompletedModuleIds("track-1")).toEqual(["lesson-1"]);

    setModuleCompletion("track-1", "lesson-1", false);
    expect(getCompletedModuleIds("track-1")).toEqual([]);
  });
});
