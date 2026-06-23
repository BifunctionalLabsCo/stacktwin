import { LessonPlayer } from "../../../components/LessonPlayer";


const PREVIEW_MODULE_IDS = [
  "small-agent-workflows",
  "rag-evaluation-first",
  "trending-repository-review",
  "technical-video-notes"
];

export const dynamicParams = false;

export function generateStaticParams() {
  return PREVIEW_MODULE_IDS.map((id) => ({ id }));
}

export default async function LessonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <LessonPlayer moduleId={id} demo />;
}
