"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, BookOpen, Check, Clock, ExternalLink } from "lucide-react";
import { markModuleComplete } from "../lib/progress";
import { fetchLessonState, type LessonState } from "../lib/weekly-track";


export function LessonPlayer({ moduleId }: { moduleId: string }) {
  const router = useRouter();
  const [state, setState] = useState<LessonState>({ status: "loading" });
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [answerChecked, setAnswerChecked] = useState(false);

  useEffect(() => {
    let active = true;
    fetchLessonState(moduleId).then((nextState) => {
      if (active) {
        setState(nextState);
      }
    });
    return () => {
      active = false;
    };
  }, [moduleId]);

  if (state.status === "loading") {
    return (
      <main className="lessonShell">
        <p className="eyebrow">Loading lesson</p>
        <div className="lessonLoading" aria-live="polite">Preparing the module...</div>
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="lessonShell">
        <Link className="backLink" href="/"><ArrowLeft size={16} /> Weekly track</Link>
        <section className="statePanel isError">
          <div><h2>Lesson unavailable</h2><p>{state.message}</p></div>
        </section>
      </main>
    );
  }

  const { lesson } = state;
  const correct = selectedAnswer === lesson.checkpoint.answer;

  function completeLesson() {
    markModuleComplete(lesson.trackId, lesson.id);
    router.push("/");
  }

  return (
    <main className="lessonShell">
      <Link className="backLink" href="/"><ArrowLeft size={16} /> Weekly track</Link>

      <header className="lessonHeader">
        <p className="eyebrow">{lesson.difficulty} module</p>
        <h1>{lesson.title}</h1>
        <div className="lessonMeta"><Clock size={16} /> {lesson.estimatedMinutes} minutes</div>
        <p className="lessonBrief">{lesson.contextBrief}</p>
      </header>

      <div className="lessonLayout">
        <article className="lessonContent">
          <section>
            <h2>Objectives</h2>
            <ul>{lesson.objectives.map((objective) => <li key={objective}>{objective}</li>)}</ul>
          </section>

          <section>
            <h2>Key concepts</h2>
            <ul>{lesson.keyConcepts.map((concept) => <li key={concept}>{concept}</li>)}</ul>
          </section>

          <section className="exerciseBlock">
            <BookOpen size={20} />
            <div><h2>{lesson.exercise.title}</h2><p>{lesson.exercise.instructions}</p></div>
          </section>

          <section>
            <h2>Checkpoint</h2>
            <p>{lesson.checkpoint.question}</p>
            <div className="answerList">
              {lesson.checkpoint.options.map((option) => (
                <label key={option}>
                  <input
                    type="radio"
                    name="checkpoint"
                    value={option}
                    checked={selectedAnswer === option}
                    onChange={() => {
                      setSelectedAnswer(option);
                      setAnswerChecked(false);
                    }}
                  />
                  <span>{option}</span>
                </label>
              ))}
            </div>
            <button
              className="secondaryAction"
              type="button"
              disabled={!selectedAnswer}
              onClick={() => setAnswerChecked(true)}
            >
              Check answer
            </button>
            {answerChecked && (
              <p className={correct ? "answerResult isCorrect" : "answerResult isIncorrect"}>
                <strong>{correct ? "Correct." : "Not quite."}</strong> {lesson.checkpoint.explanation}
              </p>
            )}
          </section>

          <section className="takeawayBlock">
            <h2>Keep this</h2>
            <p>{lesson.takeaway}</p>
          </section>

          <div className="lessonFooterActions">
            <button className="primaryAction" type="button" onClick={completeLesson}>
              <Check size={18} /> Mark complete
            </button>
            {lesson.nextModuleId && (
              <Link className="secondaryLink" href={`/lesson/${lesson.nextModuleId}/`}>
                Next lesson <ArrowRight size={16} />
              </Link>
            )}
          </div>
        </article>

        <aside className="sourceRail">
          <h2>Sources</h2>
          {lesson.sourceHints.map((source) => (
            <a href={source.url} target="_blank" rel="noreferrer" key={`${source.source}-${source.title}`}>
              <span>{source.title}</span><ExternalLink size={14} />
            </a>
          ))}
        </aside>
      </div>
    </main>
  );
}
