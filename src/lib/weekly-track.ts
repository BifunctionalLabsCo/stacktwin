import { getClassroomUserId, isDemoMode } from "./config";

export type ModuleStatus = "ready" | "queued" | "completed" | "locked" | "failed" | "stale";

export type SourceReference = {
  title: string;
  source: "hackernews" | "arxiv" | "devto" | "github_trending" | "youtube";
  url: string;
};

export type LearningModule = {
  id: string;
  title: string;
  status: ModuleStatus;
  difficulty: "Focused" | "Intermediate" | "Advanced";
  estimatedMinutes: number;
  personalizationReason: string;
  sourceHints: SourceReference[];
};

export type WeeklyTrack = {
  id: string;
  weekStart: string;
  weekLabel: string;
  generatedAt: string;
  learnerFocus: string;
  weeklyTimeBudgetMinutes: number;
  modules: LearningModule[];
};

export type WeeklyTrackState =
  | { status: "loading" }
  | { status: "profile_required"; message: string }
  | { status: "empty"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; track: WeeklyTrack };

export type LessonModule = LearningModule & {
  trackId: string;
  contextBrief: string;
  objectives: string[];
  keyConcepts: string[];
  exercise: {
    title: string;
    instructions: string;
  };
  checkpoint: {
    question: string;
    options: string[];
    answer: string;
    explanation: string;
  };
  takeaway: string;
  nextModuleId: string | null;
  availableActions: string[];
};

export type LessonState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; lesson: LessonModule };

export async function fetchWeeklyTrackState(): Promise<WeeklyTrackState> {
  try {
    const endpoint = isDemoMode()
      ? "/api/track/preview"
      : `/api/track/current?user_id=${encodeURIComponent(getClassroomUserId())}`;
    const response = await fetch(endpoint, {
      headers: { Accept: "application/json" }
    });

    if (!response.ok) {
      const payload = await readErrorPayload(response);
      if (payload.code === "profile_required") {
        return { status: "profile_required", message: payload.message };
      }
      if (payload.code === "track_not_ready") {
        return { status: "empty", message: payload.message };
      }
      return {
        status: "error",
        message: `The backend returned ${response.status} while loading this week's track.`
      };
    }

    const track = (await response.json()) as WeeklyTrack;

    if (track.modules.length === 0) {
      return {
        status: "empty",
        message: "No weekly modules are ready yet."
      };
    }

    return { status: "ready", track };
  } catch {
    return {
      status: "error",
      message: "The weekly track API could not be reached. Start the FastAPI service and retry."
    };
  }
}

export async function fetchLessonState(
  moduleId: string,
  weekStart?: string,
  demo = false
): Promise<LessonState> {
  try {
    const endpoint = demo
      ? `/api/track/preview/${encodeURIComponent(moduleId)}`
      : `/api/track/${encodeURIComponent(weekStart ?? "")}/modules/${encodeURIComponent(moduleId)}`
        + `?user_id=${encodeURIComponent(getClassroomUserId())}`;
    const response = await fetch(endpoint, {
      headers: { Accept: "application/json" }
    });

    if (!response.ok) {
      return {
        status: "error",
        message: response.status === 404 ? "This lesson could not be found." : "The lesson API failed."
      };
    }

    return {
      status: "ready",
      lesson: (await response.json()) as LessonModule
    };
  } catch {
    return {
      status: "error",
      message: "The lesson API could not be reached."
    };
  }
}

async function readErrorPayload(response: Response) {
  try {
    const payload = (await response.json()) as {
      detail?: { code?: string; message?: string };
    };
    return {
      code: payload.detail?.code ?? "unknown",
      message: payload.detail?.message ?? "The weekly track could not be loaded."
    };
  } catch {
    return { code: "unknown", message: "The weekly track could not be loaded." };
  }
}

export function getTrackProgress(track: WeeklyTrack) {
  const completedModules = track.modules.filter((module) => module.status === "completed").length;
  const plannedMinutes = track.modules.reduce(
    (total, module) => total + module.estimatedMinutes,
    0
  );
  const progressPercent =
    track.modules.length > 0 ? Math.round((completedModules / track.modules.length) * 100) : 0;

  return {
    completedModules,
    totalModules: track.modules.length,
    plannedMinutes,
    budgetMinutes: track.weeklyTimeBudgetMinutes,
    progressPercent
  };
}
