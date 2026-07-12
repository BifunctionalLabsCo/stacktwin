"use client";

import { useEffect, useState } from "react";
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
  getTrackProgress,
  type LearningModule,
  type WeeklyTrackState
} from "../lib/weekly-track";
import { applyCompletedProgress } from "../lib/progress";
import { fetchProfileInfluence, type ProfileInfluence } from "../lib/classroom";
import { useActiveClassroomUserId } from "../lib/classroom-user";
import { ProfileInfluenceBand } from "./ProfileInfluenceBand";

const statusMeta = {
  ready: { label: "Ready", Icon: CheckCircle2 },
  queued: { label: "Queued", Icon: Sparkles },
  completed: { label: "Complete", Icon: CheckCircle2 },
  locked: { label: "Waiting", Icon: Lock },
  failed: { label: "Needs review", Icon: AlertCircle },
  stale: { label: "Update available", Icon: RotateCcw }
};

export function WeeklyTrackHome() {
  const router = useRouter();
  const userId = useActiveClassroomUserId();
  const [state, setState] = useState<WeeklyTrackState>({ status: "loading" });
  const [profile, setProfile] = useState<ProfileInfluence | null>(null);

  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    setProfile(null);

    fetchWeeklyTrackState(userId).then((nextState) => {
      if (!active) {
        return;
      }
      if (nextState.status === "profile_required") {
        router.replace("/onboarding/?start=quick");
        return;
      }
      setState(
        nextState.status === "ready"
          ? { status: "ready", track: applyCompletedProgress(nextState.track) }
          : nextState
      );
    });
    fetchProfileInfluence(userId).then((nextProfile) => {
      if (active) {
        setProfile(nextProfile);
      }
    });

    return () => {
      active = false;
    };
  }, [router, userId]);

  if (state.status === "loading") {
    return (
      <main className="shell">
        <HeaderShell />
        <section className="statePanel" aria-live="polite">
          <RotateCcw size={20} />
          <div>
            <h2>Preparing this week's track</h2>
            <p>StackTwin is collecting source signals and shaping the learning cards.</p>
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
                ? "Developer profile required"
                : state.status === "empty"
                  ? "No weekly track yet"
                  : "Track unavailable"}
            </h2>
            <p>{state.message}</p>
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

function HeaderShell() {
  return (
    <section className="header">
      <div>
        <p className="eyebrow">This week's track</p>
        <h1>StackTwin</h1>
        <p className="lede">
          A compact learning module generated from live technical signals and your developer
          profile.
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
