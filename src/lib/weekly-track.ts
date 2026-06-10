export type ModuleStatus = "ready" | "queued" | "completed" | "locked" | "failed";

export type SourceReference = {
  title: string;
  source: "hackernews" | "arxiv" | "devto" | "github_trending" | "youtube";
  url: string;
};

export type LearningModule = {
  id: string;
  title: string;
  status: ModuleStatus;
  difficulty: "Focused" | "Intermediate" | "Advanced";
  estimatedMinutes: number;
  personalizationReason: string;
  sourceHints: SourceReference[];
};

export type WeeklyTrack = {
  id: string;
  weekLabel: string;
  generatedAt: string;
  learnerFocus: string;
  weeklyTimeBudgetMinutes: number;
  modules: LearningModule[];
};

export type WeeklyTrackState =
  | { status: "loading" }
  | { status: "empty"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; track: WeeklyTrack };

const demoTrack: WeeklyTrack = {
  id: "week-2026-06-08",
  weekLabel: "Week of June 8",
  generatedAt: "2026-06-08T08:00:00Z",
  learnerFocus: "Backend AI systems, RAG evaluation, and practical agent workflows",
  weeklyTimeBudgetMinutes: 150,
  modules: [
    {
      id: "small-agent-workflows",
      title: "Ship smaller AI agents",
      status: "ready",
      difficulty: "Intermediate",
      estimatedMinutes: 42,
      personalizationReason:
        "Chosen for backend engineers moving from automation scripts to production workflows.",
      sourceHints: [
        {
          title: "Agentic workflow discussion",
          source: "hackernews",
          url: "https://news.ycombinator.com/"
        },
        {
          title: "Production agent patterns",
          source: "devto",
          url: "https://dev.to/"
        }
      ]
    },
    {
      id: "rag-evaluation-first",
      title: "Evaluate RAG before adding more context",
      status: "completed",
      difficulty: "Advanced",
      estimatedMinutes: 35,
      personalizationReason:
        "A practical checkpoint for teams building retrieval systems under real constraints.",
      sourceHints: [
        {
          title: "Retrieval evaluation techniques",
          source: "arxiv",
          url: "https://arxiv.org/"
        }
      ]
    },
    {
      id: "paper-reading-loop",
      title: "Read one paper without losing the thread",
      status: "queued",
      difficulty: "Focused",
      estimatedMinutes: 28,
      personalizationReason: "A compressed research module built from this week's arXiv cluster.",
      sourceHints: [
        {
          title: "Current ML systems paper cluster",
          source: "arxiv",
          url: "https://arxiv.org/"
        }
      ]
    },
    {
      id: "github-signal-scan",
      title: "Scan one trending repo for durable ideas",
      status: "locked",
      difficulty: "Intermediate",
      estimatedMinutes: 32,
      personalizationReason:
        "Reserved for the GitHub Trending adapter once repository signals are available.",
      sourceHints: [
        {
          title: "GitHub Trending source planned",
          source: "github_trending",
          url: "https://github.com/trending"
        }
      ]
    }
  ]
};

export async function getWeeklyTrackState(): Promise<WeeklyTrackState> {
  const mode = process.env.STACKTWIN_TRACK_STATE ?? "ready";

  if (mode === "loading") {
    return { status: "loading" };
  }

  if (mode === "empty") {
    return {
      status: "empty",
      message: "No weekly track is ready yet. Generate one from the latest source ingestion run."
    };
  }

  if (mode === "error") {
    return {
      status: "error",
      message: "The weekly track could not be loaded. Check the backend source status."
    };
  }

  return {
    status: "ready",
    track: demoTrack
  };
}

export function getTrackProgress(track: WeeklyTrack) {
  const completedModules = track.modules.filter((module) => module.status === "completed").length;
  const plannedMinutes = track.modules.reduce(
    (total, module) => total + module.estimatedMinutes,
    0
  );
  const progressPercent =
    track.modules.length > 0 ? Math.round((completedModules / track.modules.length) * 100) : 0;

  return {
    completedModules,
    totalModules: track.modules.length,
    plannedMinutes,
    budgetMinutes: track.weeklyTimeBudgetMinutes,
    progressPercent
  };
}
