"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, BookOpen, CalendarDays, Clock } from "lucide-react";
import {
  fetchArchivedTrack,
  fetchTrackHistory,
  type ArchivedTrack,
  type TrackHistoryItem
} from "../lib/classroom";
import { getClassroomUserId, useActiveClassroomUserId } from "../lib/classroom-user";


type ArchiveState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; weeks: TrackHistoryItem[] };

export function ArchiveView() {
  const userId = useActiveClassroomUserId();
  const [state, setState] = useState<ArchiveState>({ status: "loading" });
  const [selected, setSelected] = useState<ArchivedTrack | null>(null);
  const [detailStatus, setDetailStatus] = useState<"idle" | "loading" | "error">("idle");

  useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    setSelected(null);
    setDetailStatus("idle");
    fetchTrackHistory(userId)
      .then((weeks) => {
        if (active) {
          setState({ status: "ready", weeks });
        }
      })
      .catch(() => {
        if (active) {
          setState({ status: "error", message: "The archive could not be loaded." });
        }
      });
    return () => {
      active = false;
    };
  }, [userId]);

  async function openWeek(weekStart: string) {
    setDetailStatus("loading");
    const requestedUserId = userId;
    try {
      const track = await fetchArchivedTrack(weekStart, requestedUserId);
      if (getClassroomUserId() !== requestedUserId) {
        return;
      }
      setSelected(track);
      setDetailStatus("idle");
    } catch {
      if (getClassroomUserId() === requestedUserId) {
        setDetailStatus("error");
      }
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
          <div><strong>No previous weeks yet</strong><p>Your first generated weekly track will appear here.</p></div>
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
                aria-pressed={selected?.weekStart === week.week_start}
              >
                <CalendarDays size={18} />
                <span><strong>{formatWeek(week.week_start)}</strong>{week.modules} modules</span>
                <small>{week.planned_minutes} min planned</small>
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
                  <div><span>Week of</span><h2>{formatWeek(selected.weekStart)}</h2></div>
                  <small>{selected.modules.length} modules</small>
                </div>
                <div className="archiveItems">
                  {selected.modules.map((module) => (
                    <article key={module.id}>
                      <div>
                        <span>{module.difficulty}</span>
                        <span><Clock size={14} /> {module.estimatedMinutes} min</span>
                      </div>
                      <h3>{module.title}</h3>
                      <p>{module.personalizationReason}</p>
                      <div className="archiveItemActions">
                        <Link
                          href={`/lesson/?week=${encodeURIComponent(selected.weekStart)}`
                            + `&module=${encodeURIComponent(module.id)}`}
                        >
                          Open lesson <ArrowRight size={15} />
                        </Link>
                        {module.sourceHints[0] && (
                          <a href={module.sourceHints[0].url} target="_blank" rel="noreferrer">
                            Source <ArrowUpRight size={15} />
                          </a>
                        )}
                      </div>
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
