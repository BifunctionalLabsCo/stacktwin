"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, FileText, RotateCcw, Sparkles, UploadCloud } from "lucide-react";
import {
  buildQuickStartProfile,
  clearOnboardingFlowState,
  createQuickStartProfileDraft,
  emptyProfile,
  loadOnboardingFlowState,
  pollLatestRun,
  saveManualProfile,
  saveOnboardingFlowState,
  triggerGeneration,
  uploadCv,
  validateCvFile,
  type QuickStartProfileDraft
} from "../lib/onboarding";
import { useActiveClassroomUserId } from "../lib/classroom-user";
import type { DeveloperProfile } from "../lib/profile-types";
import { ProfileReviewForm } from "./ProfileReviewForm";

const POLL_INTERVAL_MS = 4000;
const MAX_POLL_ATTEMPTS = 30;

type Step =
  | { name: "choose" }
  | { name: "quick"; draft: QuickStartProfileDraft }
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
  mode = "onboarding",
  startMode = "choose"
}: {
  initialProfile?: DeveloperProfile | null;
  mode?: "onboarding" | "settings";
  startMode?: "choose" | "quick";
}) {
  const router = useRouter();
  const userId = useActiveClassroomUserId();
  const [step, setStep] = useState<Step>(() => resolveInitialStep(userId, initialProfile, startMode));
  const [submitting, setSubmitting] = useState(false);
  const generationStarted = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollAttempts = useRef(0);

  useEffect(() => {
    setSubmitting(false);
    generationStarted.current = false;
    pollAttempts.current = 0;
    setStep(resolveInitialStep(userId, initialProfile, startMode));
  }, [initialProfile, startMode, userId]);

  useEffect(() => {
    if (startMode !== "quick" && !initialProfile) {
      return;
    }
    if (step.name === "quick") {
      saveOnboardingFlowState(userId, { step: "quick", draft: step.draft });
      return;
    }
    if (step.name === "review") {
      saveOnboardingFlowState(userId, { step: "review", profile: step.profile });
      return;
    }
    saveOnboardingFlowState(userId, step.name);
  }, [step, userId, startMode, initialProfile]);

  const updateQuickDraft = useCallback(
    <K extends keyof QuickStartProfileDraft>(key: K, value: QuickStartProfileDraft[K]) => {
      setStep((current) =>
        current.name === "quick" ? { name: "quick", draft: { ...current.draft, [key]: value } } : current
      );
    },
    []
  );

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

  function handleQuickStart(profileDraft: QuickStartProfileDraft) {
    if (submitting) {
      return;
    }
    setSubmitting(true);

    saveManualProfile(buildQuickStartProfile(profileDraft, userId), userId).then((result) => {
      setSubmitting(false);
      if (!result.ok) {
        setStep({ name: "error", kind: "network_error", message: result.message });
        return;
      }
      clearOnboardingFlowState(userId);
      if (mode === "settings") {
        router.replace("/");
        return;
      }
      startGeneration();
    });
  }

  function openFullEditor(profileDraft: QuickStartProfileDraft) {
    setStep({
      name: "review",
      profile: buildQuickStartProfile(profileDraft, userId),
      isUnchanged: false
    });
  }

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
      clearOnboardingFlowState(userId);
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
            onClick={() => setStep({ name: "quick", draft: createQuickStartProfileDraft(userId) })}
          >
            <Sparkles size={28} />
            <h2>Quick start</h2>
            <p>Seed a compact profile with the minimum details needed to launch a good first week.</p>
          </button>
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

  if (step.name === "quick") {
    return (
      <main className="onboardingShell">
        <OnboardingHeader />
        <p className="privacyNote">
          Enter the smallest useful profile first. You can expand the details later from the full
          profile editor.
        </p>
        <form
          className="reviewForm quickStartForm"
          aria-label="Quick start profile"
          onSubmit={(event) => {
            event.preventDefault();
            handleQuickStart(step.draft);
          }}
        >
          <div className="reviewGrid">
            <label htmlFor="quick-name">
              <span>Name</span>
              <input
                id="quick-name"
                type="text"
                value={step.draft.name}
                onChange={(event) => updateQuickDraft("name", event.target.value)}
              />
            </label>
            <label htmlFor="quick-role">
              <span>Current role</span>
              <input
                id="quick-role"
                type="text"
                value={step.draft.current_role}
                onChange={(event) => updateQuickDraft("current_role", event.target.value)}
              />
            </label>
            <label htmlFor="quick-stack" className="reviewFieldWide">
              <span>Current stack</span>
              <input
                id="quick-stack"
                type="text"
                placeholder="TypeScript, React, Next.js"
                value={step.draft.current_stack}
                onChange={(event) => updateQuickDraft("current_stack", event.target.value)}
              />
            </label>
            <label htmlFor="quick-goals" className="reviewFieldWide">
              <span>Learning goals</span>
              <input
                id="quick-goals"
                type="text"
                placeholder="Ship a sharper weekly learning flow"
                value={step.draft.learning_goals}
                onChange={(event) => updateQuickDraft("learning_goals", event.target.value)}
              />
            </label>
            <label htmlFor="quick-career" className="reviewFieldWide">
              <span>Career direction</span>
              <input
                id="quick-career"
                type="text"
                placeholder="Build a stronger product experience with AI"
                value={step.draft.career_direction}
                onChange={(event) => updateQuickDraft("career_direction", event.target.value)}
              />
            </label>
            <label htmlFor="quick-budget">
              <span>Weekly time budget (hours)</span>
              <input
                id="quick-budget"
                type="number"
                min={0.5}
                step={0.5}
                value={step.draft.weekly_time_budget_hours}
                onChange={(event) => updateQuickDraft("weekly_time_budget_hours", event.target.value)}
              />
            </label>
            <label htmlFor="quick-format">
              <span>Preferred format</span>
              <select
                id="quick-format"
                value={step.draft.preferred_format}
                onChange={(event) =>
                  updateQuickDraft("preferred_format", event.target.value as QuickStartProfileDraft["preferred_format"])
                }
              >
                <option value="">Default</option>
                <option value="short_summary">Short summary</option>
                <option value="hands_on">Hands-on</option>
                <option value="deep_dive">Deep dive</option>
                <option value="quiz">Quiz</option>
                <option value="video">Video</option>
                <option value="podcast">Podcast</option>
              </select>
            </label>
          </div>
          <div className="quickStartActions">
            <button
              type="button"
              className="secondaryAction"
              onClick={() => openFullEditor(step.draft)}
            >
              Open full editor
            </button>
            <button type="submit" className="primaryAction" disabled={submitting}>
              {submitting ? "Creating profile..." : "Create profile and generate week"}
            </button>
          </div>
        </form>
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

function resolveInitialStep(
  userId: string,
  initialProfile: DeveloperProfile | null,
  startMode: "choose" | "quick"
): Step {
  if (initialProfile) {
    return { name: "review", profile: initialProfile, isUnchanged: true };
  }

  if (startMode === "quick") {
    const stored = loadOnboardingFlowState(userId);
    if (stored?.step === "quick") {
      return { name: "quick", draft: stored.draft };
    }
    if (stored?.step === "review") {
      return { name: "review", profile: stored.profile, isUnchanged: false };
    }
  }

  return startMode === "quick"
    ? { name: "quick", draft: createQuickStartProfileDraft(userId) }
    : { name: "choose" };
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
