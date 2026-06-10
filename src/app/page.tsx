import { WeeklyTrackHome } from "../components/WeeklyTrackHome";
import { getWeeklyTrackState } from "../lib/weekly-track";

export default async function Home() {
  const state = await getWeeklyTrackState();

  return <WeeklyTrackHome state={state} />;
}
