"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, FileText, RotateCcw, UploadCloud } from "lucide-react";
import {
  emptyProfile,
  pollLatestRun,
  saveManualProfile,
  triggerGeneration,
  uploadCv,
  validateCvFile
} from "../lib/onboarding";
import { useActiveClassroomUserId } from "../lib/classroom-user";
import type { DeveloperProfile } from "../lib/profile-types";
import { ProfileReviewForm } from "./ProfileReviewForm";

const POLL_INTERVAL_MS = 4000;
const MAX_POLL_ATTEMPTS = 30;

type Step =
  | { name: "choose" }
  | { name: "uploading"; progress: number }
  | { name: "review"; profile: DeveloperProfile; isUnchanged: boolean }
  | { name: "generating" }
  | { name: "failed"; message: string }
  | {
      name: "error";
      kind: "invalid_file" | "extraction_failed" | "network_error";
      message: string;
    };

export function OnboardingFlow({
  initialProfile = null,
  mode = "onboarding"
}: {
  initialProfile?: DeveloperProfile | null;
  mode?: "onboarding" | "settings";
}) {
  const router = useRouter();
  const userId = useActiveClassroomUserId();
  const [step, setStep] = useState<Step>(
    initialProfile
      ? { name: "review", profile: initialProfile, isUnchanged: true }
      : { name: "choose" }
  );
  const [submitting, setSubmitting] = useState(false);
  const generationStarted = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollAttempts = useRef(0);

  const handleFileSelected = useCallback((file: File) => {
    const validationError = validateCvFile(file);
    if (validationError) {
      setStep({ name: "error", kind: "invalid_file", message: validationError });
      return;
    }

    setStep({ name: "uploading", progress: 0 });
    uploadCv(file, (percent) => {
      setStep((current) =>
        current.name === "uploading" ? { name: "uploading", progress: percent } : current
      );
    }, userId).then((outcome) => {
      if (outcome.status === "invalid_file" || outcome.status === "extraction_failed" || outcome.status === "network_error") {
        setStep({ name: "error", kind: outcome.status, message: outcome.message });
        return;
      }
      setStep({
        name: "review",
        profile: outcome.profile,
        isUnchanged: outcome.status === "profile-cache-hit"
      });
    });
  }, [userId]);

  const startGeneration = useCallback(() => {
    if (generationStarted.current) {
      return;
    }
    generationStarted.current = true;
    pollAttempts.current = 0;
    setStep({ name: "generating" });

    triggerGeneration(userId).then((outcome) => {
      if (outcome.status === "network_error") {
        generationStarted.current = false;
        setStep({ name: "failed", message: outcome.message });
        return;
      }
      pollUntilReady(userId);
    });
  }, [userId]);

  function pollUntilReady(activeUserId: string) {
    pollAttempts.current += 1;
    pollLatestRun(activeUserId).then((result) => {
      if (result.learnerStatus === "ready") {
        router.replace("/");
        return;
      }
      if (result.learnerStatus === "failed") {
        generationStarted.current = false;
        setStep({
          name: "failed",
          message: ("failureSummary" in result && result.failureSummary) || "Generation failed. You can retry below."
        });
        return;
      }
      if (pollAttempts.current >= MAX_POLL_ATTEMPTS) {
        generationStarted.current = false;
        setStep({
          name: "failed",
          message: "Generation is taking longer than expected. Retry to try again."
        });
        return;
      }
      setTimeout(() => pollUntilReady(activeUserId), POLL_INTERVAL_MS);
    });
  }

  function handleConfirm(profile: DeveloperProfile, isUnchanged: boolean) {
    if (submitting) {
      return;
    }
    setSubmitting(true);

    if (isUnchanged) {
      setSubmitting(false);
      if (mode === "settings") {
        router.replace("/");
        return;
      }
      startGeneration();
      return;
    }

    saveManualProfile(profile, userId).then((result) => {
      setSubmitting(false);
      if (!result.ok) {
        setStep({ name: "error", kind: "network_error", message: result.message });
        return;
      }
      if (mode === "settings") {
        router.replace("/");
        return;
      }
      startGeneration();
    });
  }

  if (step.name === "choose") {
    return (
      <main className="onboardingShell">
        <OnboardingHeader />
        <section className="onboardingChoices" aria-label="Start onboarding">
          <button
            type="button"
            className="onboardingCard"
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadCloud size={28} />
            <h2>Upload your CV</h2>
            <p>PDF or TXT. We extract role, stack, and goals to personalize your weekly track.</p>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt"
            className="visuallyHidden"
            aria-label="Upload CV file"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                handleFileSelected(file);
              }
              event.target.value = "";
            }}
          />
          <button
            type="button"
            className="onboardingCard"
            onClick={() => setStep({ name: "review", profile: emptyProfile(), isUnchanged: false })}
          >
            <FileText size={28} />
            <h2>Enter details manually</h2>
            <p>Skip the upload and fill in your role, stack, and learning goals yourself.</p>
          </button>
        </section>
      </main>
    );
  }

  if (step.name === "uploading") {
    return (
      <main className="onboardingShell">
        <OnboardingHeader />
        <section className="statePanel" aria-live="polite">
          <UploadCloud size={20} />
          <div>
            <h2>Uploading your CV</h2>
            <p>{step.progress}% uploaded. Extracting your profile next.</p>
          </div>
        </section>
      </main>
    );
  }

  if (step.name === "error") {
    return (
      <main className="onboardingShell">
        <OnboardingHeader />
        <section className="statePanel isError" role="alert">
          <AlertCircle size={20} />
          <div>
            <h2>{errorTitle(step.kind)}</h2>
            <p>{step.message}</p>
          </div>
        </section>
        <button type="button" className="secondaryAction" onClick={() => setStep({ name: "choose" })}>
          Try again
        </button>
      </main>
    );
  }

  if (step.name === "review") {
    return (
      <main className="onboardingShell">
        <OnboardingHeader />
        <p className="privacyNote">
          Your role, stack, learning goals, time budget, and format preferences shape which
          weekly modules get generated. We do not keep your raw CV text beyond this session.
        </p>
        <ProfileReviewForm
          profile={step.profile}
          submitting={submitting}
          confirmLabel={mode === "settings" ? "Save preferences" : "Confirm and generate my first week"}
          onConfirm={(profile) =>
            handleConfirm(
              profile,
              step.isUnchanged && JSON.stringify(profile) === JSON.stringify(step.profile)
            )
          }
        />
      </main>
    );
  }

  if (step.name === "generating") {
    return (
      <main className="onboardingShell">
        <OnboardingHeader />
        <section className="statePanel" aria-live="polite">
          <RotateCcw size={20} />
          <div>
            <h2>Preparing your first weekly classroom</h2>
            <p>StackTwin is collecting source signals and shaping your learning cards. This usually takes under a minute.</p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="onboardingShell">
      <OnboardingHeader />
      <section className="statePanel isError" role="alert">
        <AlertCircle size={20} />
        <div>
          <h2>Generation failed</h2>
          <p>{step.message}</p>
        </div>
      </section>
      <button type="button" className="secondaryAction" onClick={startGeneration}>
        Retry generation
      </button>
    </main>
  );
}

function OnboardingHeader() {
  return (
    <section className="header onboardingHeader">
      <div>
        <p className="eyebrow">
          <CheckCircle2 size={14} /> First-run setup
        </p>
        <h1>Set up StackTwin</h1>
        <p className="lede">
          Build your developer profile once, then jump into your personalized weekly classroom.
        </p>
      </div>
    </section>
  );
}

function errorTitle(kind: "invalid_file" | "extraction_failed" | "network_error") {
  if (kind === "invalid_file") {
    return "That file can't be used";
  }
  if (kind === "extraction_failed") {
    return "Could not read this CV";
  }
  return "Connection problem";
}
