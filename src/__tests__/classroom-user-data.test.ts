import { describe, expect, it } from "vitest";
import {
  parseConfiguredClassroomUsers,
  parseStoredClassroomUsers
} from "../lib/classroom-user-data";

describe("classroom user parsing", () => {
  it("does not inject demo users into empty custom-user storage", () => {
    expect(parseStoredClassroomUsers("")).toEqual([]);
  });

  it("keeps configured users separate from persisted custom profiles", () => {
    const configured = parseConfiguredClassroomUsers("custom@example.com|Custom");
    const stored = parseStoredClassroomUsers(
      JSON.stringify([{ id: "profile-1@stacktwin.local", label: "New Twin" }])
    );

    expect(configured.map((user) => user.id)).toEqual(["custom@example.com"]);
    expect(stored.map((user) => user.id)).toEqual(["profile-1@stacktwin.local"]);
  });
});
