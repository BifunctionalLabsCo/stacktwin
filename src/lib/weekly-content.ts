export type WeeklyContentStatus = "ready" | "pending" | "running" | "failed";

export async function ensureWeeklyContent(): Promise<WeeklyContentStatus> {
  const response = await fetch("/api/digest/prefetch/ensure", { method: "POST" });
  if (!response.ok) {
    return "failed";
  }
  const payload = (await response.json()) as { status: WeeklyContentStatus };
  return payload.status;
}
