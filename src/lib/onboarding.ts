import { getClassroomUserId } from "./config";
import type { ContentFormatValue, DeveloperProfile, ExperienceLevelValue } from "./profile-types";

export const MAX_CV_FILE_SIZE_BYTES = 5 * 1024 * 1024;
export const ACCEPTED_CV_TYPES = [".pdf", ".txt"];

export type UploadOutcome =
  | { status: "computed" | "profile-cache-hit"; profile: DeveloperProfile; sourceHash: string }
  | { status: "invalid_file"; message: string }
  | { status: "extraction_failed"; message: string }
  | { status: "network_error"; message: string };

export function validateCvFile(file: File): string | null {
  const lowerName = file.name.toLowerCase();
  const hasAcceptedExtension = ACCEPTED_CV_TYPES.some((extension) =>
    lowerName.endsWith(extension)
  );
  if (!hasAcceptedExtension) {
    return "Only PDF and TXT files are supported.";
  }
  if (file.size === 0) {
    return "This file is empty.";
  }
  if (file.size > MAX_CV_FILE_SIZE_BYTES) {
    return "File is larger than 5MB. Upload a shorter CV or use manual entry.";
  }
  return null;
}

export function uploadCv(
  file: File,
  onProgress?: (percent: number) => void,
  userId = getClassroomUserId()
): Promise<UploadOutcome> {
  return new Promise((resolve) => {
    const formData = new FormData();
    formData.append("file", file);

    const request = new XMLHttpRequest();
    request.open(
      "POST",
      `/api/profile/upload?user_id=${encodeURIComponent(userId)}`
    );

    request.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    request.onload = () => {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(request.responseText) as Record<string, unknown>;
      } catch {
        payload = {};
      }

      if (request.status === 422) {
        resolve({
          status: "extraction_failed",
          message: "Could not extract enough text from this file. Try another file or enter your profile manually."
        });
        return;
      }
      if (request.status === 400) {
        resolve({
          status: "invalid_file",
          message: typeof payload.detail === "string" ? payload.detail : "Only PDF and TXT files are supported."
        });
        return;
      }
      if (request.status < 200 || request.status >= 300) {
        resolve({
          status: "network_error",
          message: `Upload failed with status ${request.status}. Check your connection and retry.`
        });
        return;
      }

      resolve({
        status: payload.status === "profile-cache-hit" ? "profile-cache-hit" : "computed",
        profile: payload.profile as DeveloperProfile,
        sourceHash: payload.source_hash as string
      });
    };

    request.onerror = () => {
      resolve({
        status: "network_error",
        message: "Could not reach the StackTwin backend. Confirm the service is running and retry."
      });
    };

    request.send(formData);
  });
}

export async function fetchCurrentProfile(userId = getClassroomUserId()): Promise<DeveloperProfile | null> {
  try {
    const response = await fetch(
      `/api/profile/current?user_id=${encodeURIComponent(userId)}`,
      { headers: { Accept: "application/json" } }
    );
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as DeveloperProfile;
  } catch {
    return null;
  }
}

export async function saveManualProfile(
  profile: DeveloperProfile,
  userId = getClassroomUserId()
): Promise<{ ok: true; profile: DeveloperProfile } | { ok: false; message: string }> {
  try {
    const response = await fetch(
      `/api/profile/manual?user_id=${encodeURIComponent(userId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(profile)
      }
    );
    if (!response.ok) {
      return { ok: false, message: `Saving the profile failed with status ${response.status}.` };
    }
    const payload = (await response.json()) as { profile: DeveloperProfile };
    return { ok: true, profile: payload.profile };
  } catch {
    return { ok: false, message: "Could not reach the StackTwin backend. Confirm the service is running and retry." };
  }
}

export type GenerationOutcome =
  | { status: "queued" }
  | { status: "network_error"; message: string };

export async function triggerGeneration(userId = getClassroomUserId()): Promise<GenerationOutcome> {
  try {
    const response = await fetch(
      `/api/digest/run?user_id=${encodeURIComponent(userId)}`,
      { method: "POST", headers: { Accept: "application/json" } }
    );
    if (!response.ok) {
      return {
        status: "network_error",
        message: `Could not start generation (status ${response.status}). Retry in a moment.`
      };
    }
    return { status: "queued" };
  } catch {
    return {
      status: "network_error",
      message: "Could not reach the StackTwin backend to start generation. Retry in a moment."
    };
  }
}

export type RunPollResult =
  | { learnerStatus: "pending" | "ready" | "failed"; failureSummary?: string | null }
  | { learnerStatus: "unknown" };

export async function pollLatestRun(userId = getClassroomUserId()): Promise<RunPollResult> {
  try {
    const response = await fetch(
      `/api/digest/runs/latest?user_id=${encodeURIComponent(userId)}`,
      { headers: { Accept: "application/json" } }
    );
    if (response.status === 404) {
      return { learnerStatus: "pending" };
    }
    if (!response.ok) {
      return { learnerStatus: "unknown" };
    }
    const payload = (await response.json()) as {
      learner_status: "pending" | "ready" | "failed";
      failure_summary?: string | null;
    };
    return { learnerStatus: payload.learner_status, failureSummary: payload.failure_summary };
  } catch {
    return { learnerStatus: "unknown" };
  }
}

export function emptyProfile(): DeveloperProfile {
  return {
    name: null,
    current_role: null,
    experience_years: null,
    seniority: null,
    current_stack: [],
    learning: [],
    domains: [],
    certifications: [],
    career_direction: null,
    learning_goals: [],
    topics_to_track: [],
    topics_to_avoid: [],
    weekly_time_budget_hours: 5,
    preferred_formats: [],
    profile_source: "manual",
    raw_text: null
  };
}

export const EXPERIENCE_LEVELS: ExperienceLevelValue[] = ["junior", "mid", "senior", "staff"];
export const CONTENT_FORMATS: ContentFormatValue[] = [
  "short_summary",
  "hands_on",
  "deep_dive",
  "quiz",
  "video",
  "podcast"
];
