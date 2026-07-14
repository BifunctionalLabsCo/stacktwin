"use client";

import { useSearchParams } from "next/navigation";
import { OnboardingFlow } from "../../components/OnboardingFlow";

export function OnboardingRoute() {
  const searchParams = useSearchParams();
  const startMode = searchParams.get("start");
  return <OnboardingFlow startMode={startMode === "quick" ? "quick" : startMode === "new" ? "new" : "choose"} />;
}
