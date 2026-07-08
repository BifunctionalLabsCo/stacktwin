import { Suspense } from "react";
import { OnboardingFlow } from "../../components/OnboardingFlow";
import { OnboardingRoute } from "./onboarding-route";

export default function OnboardingPage() {
  return (
    <Suspense fallback={<OnboardingFlow />}>
      <OnboardingRoute />
    </Suspense>
  );
}
