"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Lock,
  RotateCcw,
  Sparkles
} from "lucide-react";
import {
  fetchWeeklyTrackState,
  fetchLatestWeeklyTrack,
  getTrackProgress,
  type LearningModule,
  type WeeklyTrackState
} from "../lib/weekly-track";
import { applyCompletedProgress } from "../lib/progress";
import { fetchProfileInfluence, type ProfileInfluence } from "../lib/classroom";
import { useActiveClassroomUserId } from "../lib/classroom-user";
import { ProfileInfluenceBand } from "./ProfileInfluenceBand";
import { ensureWeeklyContent } from "../lib/weekly-content";
import { triggerGeneration } from "../lib/onboarding";

const statusMeta = {
  ready: { label: "Ready", Icon: CheckCircle2 },
  queued: { label: "Queued", Icon: Sparkles },
  completed: { label: "Complete", Icon: CheckCircle2 },
  locked: { label: "Waiting", Icon: Lock },
  failed: { label: "Needs review", Icon: AlertCircle },
  stale: { label: "Update available", Icon: RotateCcw }
};

const CONTENT_POLL_INTERVAL_MS = 5_000;
const MAX_GENERATION_POLL_ATTEMPTS = 60;

type GenerationPhase = "idle" | "preparing_content" | "generating";

export function WeeklyTrackHome() {
  const router = useRouter();
  const userId = useActiveClassroomUserId();
  const [state, setState] = useState<WeeklyTrackState>({ status: "loading" });
  const [profile, setProfile] = useState<ProfileInfluence | null>(null);
  const [generationPhase, setGenerationPhase] = useState<GenerationPhase>("idle");
  const [generationError, setGenerationError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    setProfile(null);

    mounted.current = true;
    fetchWeeklyTrackState(userId).then(async (nextState) => {
      if (!active) {
        return;
      }
      if (nextState.status === "profile_required") {
        router.replace("/onboarding/?start=quick");
        return;
      }
      if (nextState.status === "ready") {
        setState({ status: "ready", track: applyCompletedProgress(nextState.track) });
        return;
      }
      if (nextState.status === "empty") {
        const latestTrack = await fetchLatestWeeklyTrack(userId);
        if (!active) {
          return;
        }
        setState(
          latestTrack
            ? { status: "stale", track: applyCompletedProgress(latestTrack) }
            : nextState
        );
        return;
      }
      setState(nextState);
    });
    fetchProfileInfluence(userId).then((nextProfile) => {
      if (active) {
        setProfile(nextProfile);
      }
    });

    return () => {
      active = false;
      mounted.current = false;
    };
  }, [router, userId]);

  function generateModules() {
    if (generationPhase !== "idle") {
      return;
    }
    setGenerationError(null);
    setGenerationPhase("preparing_content");

    const pollForPrefetch = async () => {
      const contentStatus = await ensureWeeklyContent();
      if (!mounted.current) {
        return;
      }
      if (contentStatus === "failed") {
        setGenerationPhase("idle");
        setGenerationError("Content preparation could not start. Try generating again in a moment.");
        return;
      }
      if (contentStatus !== "ready") {
        window.setTimeout(pollForPrefetch, CONTENT_POLL_INTERVAL_MS);
        return;
      }

      const outcome = await triggerGeneration(userId);
      if (!mounted.current) {
        return;
      }
      if (outcome.status !== "queued") {
        setGenerationPhase("idle");
        setGenerationError(outcome.message);
        return;
      }
      setGenerationPhase("generating");

      let attempts = 0;
      const pollForTrack = async () => {
        const nextState = await fetchWeeklyTrackState(userId);
        if (!mounted.current) {
          return;
        }
        if (nextState.status === "ready") {
          setState({ status: "ready", track: applyCompletedProgress(nextState.track) });
          setGenerationPhase("idle");
          return;
        }
        if (nextState.status === "profile_required") {
          router.replace("/onboarding/?start=quick");
          return;
        }
        attempts += 1;
        if (attempts >= MAX_GENERATION_POLL_ATTEMPTS) {
          setGenerationPhase("idle");
          setGenerationError("Generation is still running. Refresh shortly to see the finished modules.");
          return;
        }
        window.setTimeout(pollForTrack, CONTENT_POLL_INTERVAL_MS);
      };
      pollForTrack();
    };

    pollForPrefetch();
  }

  if (state.status === "loading" || state.status === "preparing_content") {
    return (
      <main className="shell">
        <HeaderShell />
        <section className="statePanel" aria-live="polite">
          <RotateCcw size={20} />
          <div>
            <h2>Loading your weekly track</h2>
            <p>Checking for this week’s modules and your latest available learning plan.</p>
          </div>
        </section>
        <LoadingGrid />
      </main>
    );
  }

  if (state.status === "profile_required" || state.status === "empty" || state.status === "error") {
    return (
      <main className="shell">
        <HeaderShell />
        <section className={`statePanel ${state.status === "error" ? "isError" : ""}`}>
          <AlertCircle size={20} />
          <div>
            <h2>
              {state.status === "profile_required"
                ? "Digital twin required"
                : state.status === "empty"
                  ? "No weekly track yet"
                  : "Track unavailable"}
            </h2>
            <p>
              {state.status === "empty"
                ? "Generate when you are ready. StackTwin will first collect this week’s content for every digital twin signal, then build your modules."
                : state.message}
            </p>
            {state.status !== "profile_required" && (
              <GenerationButton phase={generationPhase} onGenerate={generateModules} />
            )}
            {generationError && <p className="formError" role="alert">{generationError}</p>}
          </div>
        </section>
      </main>
    );
  }

  const { track } = state;
  const progress = getTrackProgress(track);

  return (
    <main className="shell">
      <section className="header">
        <div>
          <p className="eyebrow">{track.weekLabel}</p>
          <h1>StackTwin</h1>
          <p className="lede">{track.learnerFocus}</p>
        </div>
        <div className="tracker" aria-label="Weekly progress">
          <span>
            {progress.completedModules} of {progress.totalModules} complete
          </span>
          <strong>
            {progress.plannedMinutes} min planned of {progress.budgetMinutes} min budget
          </strong>
          <div className="meter" aria-hidden="true">
            <span style={{ width: `${progress.progressPercent}%` }} />
          </div>
        </div>
      </section>

      {state.status === "stale" && (
        <section className="statePanel" aria-live="polite">
          <RotateCcw size={20} />
          <div>
            <h2>Showing your latest available modules</h2>
            <p>This week has not been generated yet. Create it when you are ready.</p>
            <GenerationButton phase={generationPhase} onGenerate={generateModules} />
            {generationError && <p className="formError" role="alert">{generationError}</p>}
          </div>
        </section>
      )}

      <section className="summaryStrip" aria-label="Weekly track summary">
        <span>{track.modules.length} modules</span>
        <span>Updated {formatDate(track.generatedAt)}</span>
        <span>Source-backed learning cards</span>
      </section>

      {profile && <ProfileInfluenceBand profile={profile} />}

      <section className="launchGrid" aria-label="Learning launch cards">
        {track.modules.map((module) => (
          <LaunchCard module={module} weekStart={track.weekStart} key={module.id} />
        ))}
      </section>
    </main>
  );
}

function GenerationButton({ phase, onGenerate }: { phase: GenerationPhase; onGenerate: () => void }) {
  const label = phase === "preparing_content"
    ? "Preparing this week's content..."
    : phase === "generating"
      ? "Building your modules..."
      : "Generate this week's modules";
  return (
    <button type="button" className="primaryAction" onClick={onGenerate} disabled={phase !== "idle"}>
      {label}
    </button>
  );
}

function HeaderShell() {
  return (
    <section className="header">
      <div>
        <p className="eyebrow">This week's track</p>
        <h1>StackTwin</h1>
        <p className="lede">
          A compact learning module generated from live technical signals and your digital twin.
        </p>
      </div>
      <div className="tracker" aria-label="Weekly progress">
        <span>Waiting for track data</span>
        <strong>0 min planned</strong>
        <div className="meter">
          <span style={{ width: "0%" }} />
        </div>
      </div>
    </section>
  );
}

function LaunchCard({ module, weekStart }: { module: LearningModule; weekStart: string }) {
  const { Icon, label } = statusMeta[module.status];
  const isDisabled = module.status === "locked" || module.status === "failed";

  return (
    <article className={`launchCard status-${module.status}`}>
      <div className="cardTop">
        <span className="status">
          <Icon size={16} />
          {label}
        </span>
        <span className="duration">
          <Clock size={16} />
          {module.estimatedMinutes} min
        </span>
      </div>
      <div className="cardBody">
        <h2>{module.title}</h2>
        <p>{module.personalizationReason}</p>
      </div>
      <div className="sourceHints" aria-label="Source hints">
        {module.sourceHints.slice(0, 2).map((source) => (
          <a
            href={source.url}
            key={`${module.id}-${source.source}-${source.title}`}
            target="_blank"
            rel="noreferrer"
          >
            {formatSource(source.source)}
          </a>
        ))}
      </div>
      <div className="cardBottom">
        <span>{module.difficulty}</span>
        {isDisabled ? (
          <button type="button" aria-label={`${module.title} is unavailable`} disabled>
            <ArrowRight size={18} />
          </button>
        ) : (
          <Link
            href={`/lesson/?week=${encodeURIComponent(weekStart)}&module=${encodeURIComponent(module.id)}`}
            aria-label={`Launch ${module.title}`}
          >
            <ArrowRight size={18} />
          </Link>
        )}
      </div>
    </article>
  );
}

function LoadingGrid() {
  return (
    <section className="launchGrid" aria-label="Loading learning launch cards">
      {[0, 1, 2].map((item) => (
        <article className="launchCard skeletonCard" key={item}>
          <span />
          <strong />
          <p />
          <p />
        </article>
      ))}
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatSource(source: LearningModule["sourceHints"][number]["source"]) {
  const labels = {
    hackernews: "HN",
    arxiv: "arXiv",
    devto: "Dev.to",
    github_trending: "GitHub",
    youtube: "YouTube"
  };

  return labels[source];
}
