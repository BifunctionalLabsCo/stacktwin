import type { WeeklyTrack } from "./weekly-track";


const STORAGE_KEY = "stacktwin.completed-modules.v2";

type StoredProgress = Record<string, string[]>;

export function getCompletedModuleIds(trackId: string): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as StoredProgress;
    const completed = stored[trackId];
    return Array.isArray(completed)
      ? completed.filter((item) => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

export function markModuleComplete(trackId: string, moduleId: string) {
  const stored = readProgress();
  const completed = new Set(getCompletedModuleIds(trackId));
  completed.add(moduleId);
  stored[trackId] = [...completed];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  window.dispatchEvent(new Event("stacktwin-progress"));
}

export function applyCompletedProgress(track: WeeklyTrack): WeeklyTrack {
  const completed = new Set(getCompletedModuleIds(track.id));

  return {
    ...track,
    modules: track.modules.map((module) =>
      completed.has(module.id) ? { ...module, status: "completed" } : module
    )
  };
}

function readProgress(): StoredProgress {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}") as StoredProgress;
    return stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};
  } catch {
    return {};
  }
}
