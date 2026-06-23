"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, BookOpen, CalendarDays, Clock } from "lucide-react";
import {
  fetchArchivedDigest,
  fetchTrackHistory,
  type ArchivedDigest,
  type TrackHistoryItem
} from "../lib/classroom";


type ArchiveState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; weeks: TrackHistoryItem[] };

export function ArchiveView() {
  const [state, setState] = useState<ArchiveState>({ status: "loading" });
  const [selected, setSelected] = useState<ArchivedDigest | null>(null);
  const [detailStatus, setDetailStatus] = useState<"idle" | "loading" | "error">("idle");

  useEffect(() => {
    fetchTrackHistory()
      .then((weeks) => setState({ status: "ready", weeks }))
      .catch(() => setState({ status: "error", message: "The archive could not be loaded." }));
  }, []);

  async function openWeek(weekStart: string) {
    setDetailStatus("loading");
    try {
      setSelected(await fetchArchivedDigest(weekStart));
      setDetailStatus("idle");
    } catch {
      setDetailStatus("error");
    }
  }

  return (
    <main className="archiveShell">
      <header className="archiveHeader">
        <p className="eyebrow">Learning history</p>
        <h1>Weekly archive</h1>
        <p>Previous tracks stay available without competing with the current week.</p>
      </header>

      {state.status === "loading" && <div className="archiveState">Loading archive...</div>}
      {state.status === "error" && <div className="archiveState isError">{state.message}</div>}
      {state.status === "ready" && state.weeks.length === 0 && (
        <div className="archiveState">
          <BookOpen size={20} />
          <div><strong>No previous weeks yet</strong><p>Your first completed weekly digest will appear here.</p></div>
        </div>
      )}

      {state.status === "ready" && state.weeks.length > 0 && (
        <div className="archiveLayout">
          <section className="weekList" aria-label="Previous weeks">
            {state.weeks.map((week) => (
              <button
                type="button"
                key={week.week_start}
                onClick={() => openWeek(week.week_start)}
                aria-pressed={selected?.week_start === week.week_start}
              >
                <CalendarDays size={18} />
                <span><strong>{formatWeek(week.week_start)}</strong>{week.items} modules</span>
                <small>{week.total_processed} signals</small>
              </button>
            ))}
          </section>

          <section className="archiveDetail" aria-live="polite">
            {detailStatus === "loading" && <div className="archiveState">Loading week...</div>}
            {detailStatus === "error" && <div className="archiveState isError">This week could not be loaded.</div>}
            {detailStatus === "idle" && !selected && (
              <div className="archiveState">Select a week to review its learning modules.</div>
            )}
            {detailStatus === "idle" && selected && (
              <>
                <div className="archiveDetailHeader">
                  <div><span>Week of</span><h2>{formatWeek(selected.week_start)}</h2></div>
                  <small>{selected.items.length} modules</small>
                </div>
                <div className="archiveItems">
                  {selected.items.map((item) => (
                    <article key={item.url}>
                      <div><span>{item.source}</span><span><Clock size={14} /> {item.estimated_reading_minutes} min</span></div>
                      <h3>{item.title}</h3>
                      <p>{item.summary}</p>
                      <blockquote>{item.score.why_this_matters}</blockquote>
                      <a href={item.url} target="_blank" rel="noreferrer">Open source <ArrowUpRight size={15} /></a>
                    </article>
                  ))}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </main>
  );
}

function formatWeek(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" })
    .format(new Date(`${value}T12:00:00Z`));
}
