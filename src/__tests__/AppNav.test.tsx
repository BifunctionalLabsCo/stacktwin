import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppNav } from "../components/AppNav";

const pathname = vi.fn(() => "/");
const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => pathname(),
  useRouter: () => ({ push })
}));

beforeEach(() => {
  localStorage.clear();
  pathname.mockReturnValue("/");
  push.mockClear();
});

afterEach(() => {
  cleanup();
});

describe("AppNav learner switcher", () => {
  it("persists the active learner selection in localStorage", async () => {
    const user = userEvent.setup();

    render(<AppNav />);

    const switcher = screen.getByLabelText(/switch active learner/i);
    expect(switcher).toHaveValue("engineer@stacktwin.dev");

    await user.selectOptions(switcher, "researcher@stacktwin.dev");

    expect(switcher).toHaveValue("researcher@stacktwin.dev");
    expect(localStorage.getItem("stacktwin.active-user-id")).toBe("researcher@stacktwin.dev");

    cleanup();
    render(<AppNav />);

    expect(screen.getByLabelText(/switch active learner/i)).toHaveValue("researcher@stacktwin.dev");
    expect(screen.getByRole("button", { name: /new profile/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /new profile/i }));

    expect(push).toHaveBeenCalledWith("/onboarding/?start=new");
    expect(localStorage.getItem("stacktwin.active-user-id")).toMatch(/^profile-.+@stacktwin\.local$/);
  });
});
