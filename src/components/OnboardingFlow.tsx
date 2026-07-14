"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, FileText, Palette, Search, Sparkles, UploadCloud, Wrench } from "lucide-react";
import {
  buildQuickStartProfile,
  clearOnboardingFlowState,
  createNewProfile,
  createQuickStartProfileDraft,
  emptyProfile,
  loadOnboardingFlowState,
  PROFILE_PRESETS,
  saveManualProfile,
  saveOnboardingFlowState,
  uploadCv,
  validateCvFile,
  type QuickStartProfileDraft
} from "../lib/onboarding";
import { useActiveClassroomUserId } from "../lib/classroom-user";
import type { DeveloperProfile } from "../lib/profile-types";
import { ProfileReviewForm } from "./ProfileReviewForm";

type Step =
  | { name: "choose" }
  | { name: "quick"; draft: QuickStartProfileDraft }
  | { name: "uploading"; progress: number }
  | { name: "processing" }
  | { name: "review"; profile: DeveloperProfile; isUnchanged: boolean }
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
  startMode?: "choose" | "quick" | "new";
}) {
  const router = useRouter();
  const userId = useActiveClassroomUserId();
  const [step, setStep] = useState<Step>(() => resolveInitialStep(userId, initialProfile, startMode));
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setSubmitting(false);
    setStep(resolveInitialStep(userId, initialProfile, startMode));
  }, [initialProfile, startMode, userId]);

  useEffect(() => {
    if (startMode === "choose" && !initialProfile) {
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
    }, () => setStep({ name: "processing" }), userId).then((outcome) => {
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
      router.replace("/");
    });
  }

  function openFullEditor(profileDraft: QuickStartProfileDraft) {
    setStep({
      name: "review",
      profile: buildQuickStartProfile(profileDraft, userId),
      isUnchanged: false
    });
  }

  function handleConfirm(profile: DeveloperProfile, isUnchanged: boolean) {
    if (submitting) {
      return;
    }
    setSubmitting(true);

    if (isUnchanged) {
      setSubmitting(false);
      router.replace("/");
      return;
    }

    saveManualProfile(profile, userId).then((result) => {
      setSubmitting(false);
      if (!result.ok) {
        setStep({ name: "error", kind: "network_error", message: result.message });
        return;
      }
      clearOnboardingFlowState(userId);
      router.replace("/");
    });
  }

  if (step.name === "choose") {
    return (
      <main className="onboardingShell">
        <OnboardingHeader />
        <section className="profilePresetSection" aria-labelledby="profile-presets-heading">
          <div className="sectionIntro">
            <p className="eyebrow">Choose a starting point</p>
            <h2 id="profile-presets-heading">Bootstrap a learning profile</h2>
            <p>Pick the profile that best matches how you learn today. You can edit every detail before saving.</p>
          </div>
          <div className="profilePresetGrid">
            {PROFILE_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                className="profilePresetCard"
                onClick={() => setStep({ name: "quick", draft: createQuickStartProfileDraft(userId, preset.id) })}
              >
                <PresetIcon preset={preset.id} />
                <span className="profilePresetLabel">{preset.label}</span>
                <span className="profilePresetDescription">{preset.description}</span>
                <span className="profilePresetAction">Quick bootstrap <span aria-hidden="true">→</span></span>
              </button>
            ))}
            <button
              type="button"
              className="profilePresetCard isNew"
              onClick={() => setStep({ name: "review", profile: emptyProfile(), isUnchanged: false })}
            >
              <FileText size={24} />
              <span className="profilePresetLabel">New Profile</span>
              <span className="profilePresetDescription">Start from a blank profile and shape it yourself.</span>
              <span className="profilePresetAction">Create from scratch <span aria-hidden="true">→</span></span>
            </button>
          </div>
        </section>
        <p className="onboardingDivider">Or build one from an existing source</p>
        <section className="onboardingChoices" aria-label="Other profile setup options">
          <button
            type="button"
            className="onboardingCard"
            onClick={() => setStep({ name: "quick", draft: createQuickStartProfileDraft(userId) })}
          >
            <Sparkles size={28} />
            <h2>Quick start editor</h2>
            <p>Use a compact form when you want to customize a profile before saving it.</p>
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
              {submitting ? "Creating profile..." : "Create profile"}
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
            <p>{step.progress}% uploaded. We will read and structure it next.</p>
          </div>
        </section>
      </main>
    );
  }

  if (step.name === "processing") {
    return (
      <main className="onboardingShell">
        <OnboardingHeader />
        <section className="statePanel" aria-live="polite">
          <Search size={20} />
          <div>
            <h2>Reading your CV</h2>
            <p>Extracting the useful signals and preparing your learning profile.</p>
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
          Your role, stack, learning goals, and time budget shape which
          weekly modules get generated. We do not keep your raw CV text beyond this session.
        </p>
        <ProfileReviewForm
          profile={step.profile}
          submitting={submitting}
          confirmLabel={mode === "settings" ? "Save preferences" : "Confirm profile"}
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

  return null;
}

function PresetIcon({ preset }: { preset: "engineer" | "creator" | "researcher" }) {
  if (preset === "creator") {
    return <Palette size={24} />;
  }
  if (preset === "researcher") {
    return <Search size={24} />;
  }
  return <Wrench size={24} />;
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
  startMode: "choose" | "quick" | "new"
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

  if (startMode === "new") {
    return { name: "review", profile: createNewProfile(userId), isUnchanged: false };
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
