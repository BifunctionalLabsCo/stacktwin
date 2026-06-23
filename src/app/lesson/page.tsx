"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { LessonPlayer } from "../../components/LessonPlayer";

function CurrentLesson() {
  const params = useSearchParams();
  const weekStart = params.get("week");
  const moduleId = params.get("module");

  if (!weekStart || !moduleId) {
    return (
      <main className="lessonShell">
        <Link className="backLink" href="/"><ArrowLeft size={16} /> Weekly track</Link>
        <section className="statePanel isError">
          <div><h2>Lesson link incomplete</h2><p>Return to the weekly track and launch the module again.</p></div>
        </section>
      </main>
    );
  }

  return <LessonPlayer moduleId={moduleId} weekStart={weekStart} />;
}

export default function CurrentLessonPage() {
  return (
    <Suspense fallback={<main className="lessonShell"><div className="lessonLoading">Loading lesson...</div></main>}>
      <CurrentLesson />
    </Suspense>
  );
}
