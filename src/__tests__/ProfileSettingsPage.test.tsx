import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ProfileSettingsPage from "../app/profile/page";
import { setClassroomUserId } from "../lib/classroom-user";
import type { DeveloperProfile } from "../lib/profile-types";

const replace = vi.fn();

const { fetchCurrentProfile } = vi.hoisted(() => ({
  fetchCurrentProfile: vi.fn(async (userId: string): Promise<DeveloperProfile | null> => {
    if (userId === "demo@stacktwin.dev") {
      return {
        name: "Demo Learner",
        current_role: "Product Engineer",
        experience_years: 6,
        seniority: "senior",
        current_stack: ["TypeScript", "Next.js"],
        learning: ["better onboarding"],
        domains: ["edtech"],
        certifications: [],
        career_direction: "Improve first-run product flows",
        learning_goals: ["ship a quick profile setup"],
        topics_to_track: ["onboarding"],
        topics_to_avoid: [],
        weekly_time_budget_hours: 4,
        preferred_formats: ["hands_on"],
        profile_source: "manual",
        raw_text: null
      };
    }
    if (userId === "soumya@gmail.com") {
      return {
        name: "Soumya",
        current_role: "Staff Engineer",
        experience_years: 10,
        seniority: "staff",
        current_stack: ["React", "GraphQL"],
        learning: ["frontend architecture"],
        domains: ["platform"],
        certifications: [],
        career_direction: "Lead a modern frontend platform",
        learning_goals: ["scale the onboarding system"],
        topics_to_track: ["frontend"],
        topics_to_avoid: [],
        weekly_time_budget_hours: 5,
        preferred_formats: ["deep_dive"],
        profile_source: "manual",
        raw_text: null
      };
    }
    return null;
  })
}));

vi.mock(import("../lib/onboarding"), async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/onboarding")>();
  return { ...actual, fetchCurrentProfile };
});
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace })
}));

beforeEach(() => {
  localStorage.clear();
  fetchCurrentProfile.mockClear();
  replace.mockClear();
});

afterEach(() => {
  cleanup();
});

describe("ProfileSettingsPage missing-profile and reload states", () => {
  it("offers quick onboarding when the active learner has no profile", async () => {
    await act(async () => {
      setClassroomUserId("john@company.com");
    });

    render(<ProfileSettingsPage />);

    expect(await screen.findByRole("link", { name: /quick start/i })).toHaveAttribute(
      "href",
      "/onboarding?start=quick"
    );
    expect(screen.getByRole("link", { name: /full onboarding/i })).toHaveAttribute(
      "href",
      "/onboarding"
    );
  });

  it("reloads the saved profile when the active learner changes", async () => {
    render(<ProfileSettingsPage />);

    expect(await screen.findByLabelText(/^name$/i)).toHaveValue("Demo Learner");
    expect(fetchCurrentProfile).toHaveBeenCalledWith("demo@stacktwin.dev");

    await act(async () => {
      setClassroomUserId("soumya@gmail.com");
    });

    await waitFor(() => expect(fetchCurrentProfile).toHaveBeenCalledWith("soumya@gmail.com"));
    await waitFor(() => expect(screen.getByLabelText(/^name$/i)).toHaveValue("Soumya"));
  });
});
