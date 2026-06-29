import {
  getDefaultClassroomUsers,
  normalizeClassroomUserId,
  parseConfiguredClassroomUsers
} from "./classroom-user-data";

const CLASSROOM_USERS = parseConfiguredClassroomUsers(process.env.NEXT_PUBLIC_STACKTWIN_DEMO_USERS);
const DEFAULT_USERS = getDefaultClassroomUsers();
const DEFAULT_USER_ID = CLASSROOM_USERS[0]?.id ?? DEFAULT_USERS[0].id;
const STORAGE_KEY = "stacktwin.active-user-id";

export function getClassroomUserId() {
  if (typeof window === "undefined") {
    return DEFAULT_USER_ID;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  return normalizeClassroomUserId(stored, CLASSROOM_USERS);
}

export function isDemoMode() {
  return process.env.NEXT_PUBLIC_STACKTWIN_DEMO_MODE === "true";
}
