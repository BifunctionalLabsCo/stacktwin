import type { WeeklyTrack } from "./weekly-track";


const STORAGE_KEY = "stacktwin.completed-modules";

export function getCompletedModuleIds(): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(stored) ? stored.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

export function markModuleComplete(moduleId: string) {
  const completed = new Set(getCompletedModuleIds());
  completed.add(moduleId);
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...completed]));
  window.dispatchEvent(new Event("stacktwin-progress"));
}

export function applyCompletedProgress(track: WeeklyTrack): WeeklyTrack {
  const completed = new Set(getCompletedModuleIds());

  return {
    ...track,
    modules: track.modules.map((module) =>
      completed.has(module.id) ? { ...module, status: "completed" } : module
    )
  };
}
