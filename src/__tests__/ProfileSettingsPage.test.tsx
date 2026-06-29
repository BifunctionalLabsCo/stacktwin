import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ProfileSettingsPage from "../app/profile/page";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/profile"
}));

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body
  } as Response;
}

beforeEach(() => {
  replace.mockClear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ProfileSettingsPage missing profile state", () => {
  it("renders quick-start onboarding when no profile exists", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(null))
    );

    render(<ProfileSettingsPage />);

    await waitFor(() =>
      expect(screen.getByLabelText(/quick start profile setup/i)).toBeInTheDocument()
    );
  });
});
