import type { ProfileInfluence } from "../lib/classroom";


export function ProfileInfluenceBand({ profile }: { profile: ProfileInfluence }) {
  const signals = [...profile.currentStack.slice(0, 3), ...profile.learning.slice(0, 2)];

  return (
    <section className="influenceBand" aria-label="Profile influence">
      <div>
        <span>Personalized for</span>
        <strong>{profile.name || profile.currentRole || "your developer profile"}</strong>
      </div>
      {profile.careerDirection && <p>{profile.careerDirection}</p>}
      {signals.length > 0 && (
        <div className="influenceSignals" aria-label="Profile signals">
          {signals.map((signal) => <span key={signal}>{signal}</span>)}
        </div>
      )}
    </section>
  );
}
