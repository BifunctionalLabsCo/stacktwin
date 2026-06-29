"use client";

import { useEffect, useState } from "react";
import { fetchCurrentProfile } from "../../lib/onboarding";
import type { DeveloperProfile } from "../../lib/profile-types";
import { OnboardingFlow } from "../../components/OnboardingFlow";
import { useActiveClassroomUserId } from "../../lib/classroom-user";

type LoadState =
  | { status: "loading" }
  | { status: "missing" }
  | { status: "ready"; profile: DeveloperProfile };

export default function ProfileSettingsPage() {
  const userId = useActiveClassroomUserId();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    fetchCurrentProfile(userId).then((profile) => {
      if (!active) {
        return;
      }
      setState(profile ? { status: "ready", profile } : { status: "missing" });
    });
    return () => {
      active = false;
    };
  }, [userId]);

  if (state.status === "loading") {
    return (
      <main className="onboardingShell">
        <p>Loading your profile…</p>
      </main>
    );
  }

  if (state.status === "missing") {
    return <OnboardingFlow initialView="quick-start" />;
  }

  return <OnboardingFlow initialProfile={state.profile} mode="settings" />;
}
