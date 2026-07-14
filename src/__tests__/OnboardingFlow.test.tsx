import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingFlow } from "../components/OnboardingFlow";
import { setClassroomUserId } from "../lib/classroom-user";
import { emptyProfile } from "../lib/onboarding";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace })
}));

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body
  } as Response;
}

class FakeXHR {
  static instances: FakeXHR[] = [];
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  status = 200;
  responseText = "{}";

  open() {}
  send() {
    FakeXHR.instances.push(this);
  }
}

beforeEach(() => {
  replace.mockClear();
  FakeXHR.instances = [];
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("OnboardingFlow manual entry path", () => {
  it("walks through manual entry, review, and profile confirmation to the classroom", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/api/profile/manual")) {
        const body = JSON.parse(init?.body as string);
        return jsonResponse({ status: "ok", user_id: "demo", profile: body });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<OnboardingFlow />);

    await user.click(screen.getByRole("button", { name: /enter details manually/i }));

    expect(await screen.findByLabelText(/developer profile review/i)).toBeInTheDocument();

    await user.type(screen.getByLabelText(/^name$/i), "Ada Lovelace");
    await user.click(screen.getByRole("button", { name: /confirm profile/i }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/profile/manual"),
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/api/digest/run"),
      expect.anything()
    );
  });
});

describe("OnboardingFlow quick start path", () => {
  it("offers Engineer, Creator, Researcher, and New Profile bootstrap paths", async () => {
    const user = userEvent.setup();

    render(<OnboardingFlow />);

    expect(screen.getByRole("button", { name: /engineer/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /creator/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /researcher/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new profile/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /creator/i }));

    expect(await screen.findByLabelText(/quick start profile/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^current role$/i)).toHaveValue("AI Content Creator");
  });

  it("saves a compact seeded profile without starting generation", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/api/profile/manual")) {
        const body = JSON.parse(init?.body as string) as Record<string, unknown>;
        expect(body.current_role).toBe("Full-stack Engineer");
        expect(body.current_stack).toEqual(["FastAPI", "Supabase", "React"]);
        expect(body.preferred_formats).toEqual([]);
        return jsonResponse({ status: "ok", user_id: "demo", profile: body });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<OnboardingFlow startMode="quick" />);

    expect(await screen.findByLabelText(/quick start profile/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/preferred format/i)).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^name$/i));
    await user.type(screen.getByLabelText(/^name$/i), "Ada Lovelace");
    await user.type(screen.getByLabelText(/learning goals/i), ", deepen product instincts");
    await user.click(screen.getByRole("button", { name: /create profile/i }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/profile/manual"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("restores an in-progress draft per active learner", async () => {
    const user = userEvent.setup();
    setClassroomUserId("engineer@stacktwin.dev");

    render(<OnboardingFlow startMode="quick" />);

    await user.clear(screen.getByLabelText(/^name$/i));
    await user.type(screen.getByLabelText(/^name$/i), "Demo Draft");
    await waitFor(() => expect(screen.getByLabelText(/^name$/i)).toHaveValue("Demo Draft"));

    await act(async () => {
      setClassroomUserId("creator@stacktwin.dev");
    });

    await waitFor(() => expect(screen.getByLabelText(/^name$/i)).toHaveValue("Creator"));

    await user.clear(screen.getByLabelText(/^name$/i));
    await user.type(screen.getByLabelText(/^name$/i), "Creator Draft");
    await waitFor(() => expect(screen.getByLabelText(/^name$/i)).toHaveValue("Creator Draft"));

    await act(async () => {
      setClassroomUserId("engineer@stacktwin.dev");
    });

    await waitFor(() => expect(screen.getByLabelText(/^name$/i)).toHaveValue("Demo Draft"));
  });
});

describe("OnboardingFlow error recovery", () => {
  it("rejects an unsupported file type before uploading", async () => {
    render(<OnboardingFlow />);

    const input = screen.getByLabelText(/upload cv file/i);
    const badFile = new File(["hello"], "resume.docx", { type: "application/msword" });

    fireEvent.change(input, { target: { files: [badFile] } });

    expect(await screen.findByText(/only pdf and txt files/i)).toBeInTheDocument();
  });

  it("shows a network error recovery action when the manual save fails", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      })
    );

    render(<OnboardingFlow initialProfile={emptyProfile()} />);

    await user.type(screen.getByLabelText(/^name$/i), "Ada");
    await user.click(screen.getByRole("button", { name: /confirm profile/i }));

    expect(
      await screen.findByText(/could not reach the stacktwin backend/i)
    ).toBeInTheDocument();
  });

});

describe("OnboardingFlow CV upload happy path", () => {
  it("uploads a valid file and reaches the review step", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("XMLHttpRequest", FakeXHR as unknown as typeof XMLHttpRequest);

    render(<OnboardingFlow />);

    const input = screen.getByLabelText(/upload cv file/i);
    const file = new File(["a".repeat(200)], "resume.txt", { type: "text/plain" });

    await user.upload(input, file);

    await waitFor(() => expect(FakeXHR.instances.length).toBe(1));
    const instance = FakeXHR.instances[0];
    instance.status = 200;
    instance.responseText = JSON.stringify({
      status: "computed",
      source_hash: "abc",
      profile: emptyProfile()
    });
    instance.onload?.();

    expect(await screen.findByLabelText(/developer profile review/i)).toBeInTheDocument();
  });
});
