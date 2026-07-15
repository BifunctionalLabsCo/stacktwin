import type { ProfileInfluence } from "../lib/classroom";


export function ProfileInfluenceBand({ profile }: { profile: ProfileInfluence }) {
  const signals = [...profile.currentStack.slice(0, 3), ...profile.learning.slice(0, 2)];

  return (
    <section className="influenceBand" aria-label="Digital twin influence">
      <div>
        <span>Personalized for</span>
        <strong>{profile.name || profile.currentRole || "your digital twin"}</strong>
      </div>
      {profile.careerDirection && <p>{profile.careerDirection}</p>}
      {signals.length > 0 && (
        <div className="influenceSignals" aria-label="Digital twin signals">
          {signals.map((signal) => <span key={signal}>{signal}</span>)}
        </div>
      )}
    </section>
  );
}
