export function getClassroomUserId() {
  return process.env.NEXT_PUBLIC_STACKTWIN_USER_ID ?? "demo@stacktwin.dev";
}

export function isDemoMode() {
  return process.env.NEXT_PUBLIC_STACKTWIN_DEMO_MODE === "true";
}
