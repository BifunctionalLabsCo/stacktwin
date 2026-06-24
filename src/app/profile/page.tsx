"use client";

import { useEffect, useState } from "react";
import { fetchCurrentProfile } from "../../lib/onboarding";
import type { DeveloperProfile } from "../../lib/profile-types";
import { OnboardingFlow } from "../../components/OnboardingFlow";

type LoadState =
  | { status: "loading" }
  | { status: "missing" }
  | { status: "ready"; profile: DeveloperProfile };

export default function ProfileSettingsPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    fetchCurrentProfile().then((profile) => {
      if (!active) {
        return;
      }
      setState(profile ? { status: "ready", profile } : { status: "missing" });
    });
    return () => {
      active = false;
    };
  }, []);

  if (state.status === "loading") {
    return (
      <main className="onboardingShell">
        <p>Loading your profile…</p>
      </main>
    );
  }

  if (state.status === "missing") {
    return (
      <main className="onboardingShell">
        <section className="statePanel isError" role="alert">
          <div>
            <h2>No profile found</h2>
            <p>Complete onboarding first to create a developer profile.</p>
          </div>
        </section>
      </main>
    );
  }

  return <OnboardingFlow initialProfile={state.profile} mode="settings" />;
}
