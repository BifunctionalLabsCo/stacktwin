export type ProfileInfluence = {
  name: string | null;
  currentRole: string | null;
  currentStack: string[];
  learning: string[];
  careerDirection: string | null;
};

export type TrackHistoryItem = {
  week_start: string;
  generated_at: string;
  items: number;
  total_processed: number;
};

export type DigestItem = {
  title: string;
  url: string;
  source: string;
  summary: string;
  estimated_reading_minutes: number;
  score: {
    overall: number;
    why_this_matters: string;
  };
};

export type ArchivedDigest = {
  week_start: string;
  profile_name: string | null;
  items: DigestItem[];
  total_items_processed: number;
  generated_at: string;
};

type ProfilePayload = {
  name?: string | null;
  current_role?: string | null;
  current_stack?: string[];
  learning?: string[];
  career_direction?: string | null;
};

export function getClassroomUserId() {
  return process.env.NEXT_PUBLIC_STACKTWIN_USER_ID ?? "demo@stacktwin.dev";
}

export async function fetchProfileInfluence(): Promise<ProfileInfluence | null> {
  const response = await fetch(
    `/api/profile/current?user_id=${encodeURIComponent(getClassroomUserId())}`,
    { headers: { Accept: "application/json" } }
  );
  if (!response.ok) {
    return null;
  }
  const profile = (await response.json()) as ProfilePayload;
  return {
    name: profile.name ?? null,
    currentRole: profile.current_role ?? null,
    currentStack: profile.current_stack ?? [],
    learning: profile.learning ?? [],
    careerDirection: profile.career_direction ?? null
  };
}

export async function fetchTrackHistory(): Promise<TrackHistoryItem[]> {
  const response = await fetch(
    `/api/track/history?user_id=${encodeURIComponent(getClassroomUserId())}`,
    { headers: { Accept: "application/json" } }
  );
  if (!response.ok) {
    throw new Error(`History request failed with ${response.status}`);
  }
  const payload = (await response.json()) as { weeks: TrackHistoryItem[] };
  return payload.weeks;
}

export async function fetchArchivedDigest(weekStart: string): Promise<ArchivedDigest> {
  const response = await fetch(
    `/api/track/history/${encodeURIComponent(weekStart)}?user_id=${encodeURIComponent(getClassroomUserId())}`,
    { headers: { Accept: "application/json" } }
  );
  if (!response.ok) {
    throw new Error(`Archived digest request failed with ${response.status}`);
  }
  return (await response.json()) as ArchivedDigest;
}
