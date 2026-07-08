"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
    return (
      <main className="onboardingShell">
        <section className="statePanel isError" role="alert">
          <div>
            <h2>No profile found</h2>
            <p>Start with a quick demo profile or open the full onboarding flow for this learner.</p>
            <div className="profileFallbackActions">
              <Link className="secondaryAction" href="/onboarding/?start=quick">
                Quick start
              </Link>
              <Link className="secondaryAction" href="/onboarding/">
                Full onboarding
              </Link>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return <OnboardingFlow initialProfile={state.profile} mode="settings" />;
}
