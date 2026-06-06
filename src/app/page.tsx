import { ArrowRight, CheckCircle2, Clock, Sparkles } from "lucide-react";

const modules = [
  {
    title: "Ship smaller AI agents",
    reason: "Chosen for backend engineers moving from automation scripts to production workflows.",
    duration: "42 min",
    level: "Intermediate",
    status: "Ready"
  },
  {
    title: "Evaluate RAG before adding more context",
    reason: "A practical checkpoint for teams building retrieval systems under real constraints.",
    duration: "35 min",
    level: "Advanced",
    status: "Ready"
  },
  {
    title: "Read one paper without losing the thread",
    reason: "A compressed research module built from this week's arXiv cluster.",
    duration: "28 min",
    level: "Focused",
    status: "Queued"
  }
];

export default function Home() {
  return (
    <main className="shell">
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
          <span>2 of 5 complete</span>
          <strong>96 min planned</strong>
          <div className="meter">
            <span />
          </div>
        </div>
      </section>

      <section className="launchGrid" aria-label="Learning launch cards">
        {modules.map((module) => (
          <article className="launchCard" key={module.title}>
            <div className="cardTop">
              <span className="status">
                {module.status === "Ready" ? <CheckCircle2 size={16} /> : <Sparkles size={16} />}
                {module.status}
              </span>
              <span className="duration">
                <Clock size={16} />
                {module.duration}
              </span>
            </div>
            <h2>{module.title}</h2>
            <p>{module.reason}</p>
            <div className="cardBottom">
              <span>{module.level}</span>
              <button type="button" aria-label={`Launch ${module.title}`}>
                <ArrowRight size={18} />
              </button>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
