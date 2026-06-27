import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppNav } from "../components/AppNav";

const pathname = vi.fn(() => "/");

vi.mock("next/navigation", () => ({
  usePathname: () => pathname()
}));

beforeEach(() => {
  localStorage.clear();
  pathname.mockReturnValue("/");
});

afterEach(() => {
  cleanup();
});

describe("AppNav learner switcher", () => {
  it("persists the active learner selection in localStorage", async () => {
    const user = userEvent.setup();

    render(<AppNav />);

    const switcher = screen.getByLabelText(/switch active learner/i);
    expect(switcher).toHaveValue("demo@stacktwin.dev");

    await user.selectOptions(switcher, "john@company.com");

    expect(switcher).toHaveValue("john@company.com");
    expect(localStorage.getItem("stacktwin.active-user-id")).toBe("john@company.com");

    cleanup();
    render(<AppNav />);

    expect(screen.getByLabelText(/switch active learner/i)).toHaveValue("john@company.com");
  });
});
