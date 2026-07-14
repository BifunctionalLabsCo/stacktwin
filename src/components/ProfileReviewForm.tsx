"use client";

import { useEffect, useId, useState } from "react";
import { EXPERIENCE_LEVELS } from "../lib/onboarding";
import type { DeveloperProfile } from "../lib/profile-types";

function toListInput(values: string[]) {
  return values.join(", ");
}

function fromListInput(value: string) {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

export function ProfileReviewForm({
  profile,
  onConfirm,
  submitting,
  confirmLabel
}: {
  profile: DeveloperProfile;
  onConfirm: (profile: DeveloperProfile) => void;
  submitting: boolean;
  confirmLabel: string;
}) {
  const [draft, setDraft] = useState(profile);
  const idPrefix = useId();

  useEffect(() => {
    setDraft(profile);
  }, [profile]);

  function update<K extends keyof DeveloperProfile>(key: K, value: DeveloperProfile[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  return (
    <form
      className="reviewForm"
      aria-label="Developer profile review"
      onSubmit={(event) => {
        event.preventDefault();
        onConfirm(draft);
      }}
    >
      <div className="reviewGrid">
        <label htmlFor={`${idPrefix}-name`}>
          <span>Name</span>
          <input
            id={`${idPrefix}-name`}
            type="text"
            value={draft.name ?? ""}
            onChange={(event) => update("name", event.target.value || null)}
          />
        </label>

        <label htmlFor={`${idPrefix}-role`}>
          <span>Current role</span>
          <input
            id={`${idPrefix}-role`}
            type="text"
            value={draft.current_role ?? ""}
            onChange={(event) => update("current_role", event.target.value || null)}
          />
        </label>

        <label htmlFor={`${idPrefix}-seniority`}>
          <span>Experience level</span>
          <select
            id={`${idPrefix}-seniority`}
            value={draft.seniority ?? ""}
            onChange={(event) =>
              update("seniority", (event.target.value || null) as DeveloperProfile["seniority"])
            }
          >
            <option value="">Select level</option>
            {EXPERIENCE_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>

        <label htmlFor={`${idPrefix}-years`}>
          <span>Years of experience</span>
          <input
            id={`${idPrefix}-years`}
            type="number"
            min={0}
            value={draft.experience_years ?? ""}
            onChange={(event) =>
              update(
                "experience_years",
                event.target.value === "" ? null : Number(event.target.value)
              )
            }
          />
        </label>

        <label htmlFor={`${idPrefix}-stack`} className="reviewFieldWide">
          <span>Current stack</span>
          <input
            id={`${idPrefix}-stack`}
            type="text"
            placeholder="TypeScript, Postgres, AWS"
            value={toListInput(draft.current_stack)}
            onChange={(event) => update("current_stack", fromListInput(event.target.value))}
          />
        </label>

        <label htmlFor={`${idPrefix}-domains`} className="reviewFieldWide">
          <span>Domains</span>
          <input
            id={`${idPrefix}-domains`}
            type="text"
            placeholder="Fintech, developer tools"
            value={toListInput(draft.domains)}
            onChange={(event) => update("domains", fromListInput(event.target.value))}
          />
        </label>

        <label htmlFor={`${idPrefix}-learning`} className="reviewFieldWide">
          <span>Currently learning</span>
          <input
            id={`${idPrefix}-learning`}
            type="text"
            placeholder="Rust, distributed systems"
            value={toListInput(draft.learning)}
            onChange={(event) => update("learning", fromListInput(event.target.value))}
          />
        </label>

        <label htmlFor={`${idPrefix}-goals`} className="reviewFieldWide">
          <span>Learning goals</span>
          <input
            id={`${idPrefix}-goals`}
            type="text"
            placeholder="Ship a production agent, learn systems design"
            value={toListInput(draft.learning_goals)}
            onChange={(event) => update("learning_goals", fromListInput(event.target.value))}
          />
        </label>

        <label htmlFor={`${idPrefix}-topics-track`} className="reviewFieldWide">
          <span>Topics to track</span>
          <input
            id={`${idPrefix}-topics-track`}
            type="text"
            placeholder="LLM agents, vector databases"
            value={toListInput(draft.topics_to_track)}
            onChange={(event) => update("topics_to_track", fromListInput(event.target.value))}
          />
        </label>

        <label htmlFor={`${idPrefix}-topics-avoid`} className="reviewFieldWide">
          <span>Topics to avoid</span>
          <input
            id={`${idPrefix}-topics-avoid`}
            type="text"
            placeholder="Front-end frameworks"
            value={toListInput(draft.topics_to_avoid)}
            onChange={(event) => update("topics_to_avoid", fromListInput(event.target.value))}
          />
        </label>

        <label htmlFor={`${idPrefix}-career`} className="reviewFieldWide">
          <span>Career direction</span>
          <input
            id={`${idPrefix}-career`}
            type="text"
            placeholder="Move toward staff infrastructure engineering"
            value={draft.career_direction ?? ""}
            onChange={(event) => update("career_direction", event.target.value || null)}
          />
        </label>

        <label htmlFor={`${idPrefix}-budget`}>
          <span>Weekly time budget (hours)</span>
          <input
            id={`${idPrefix}-budget`}
            type="number"
            min={0.5}
            step={0.5}
            value={draft.weekly_time_budget_hours}
            onChange={(event) => update("weekly_time_budget_hours", Number(event.target.value))}
          />
        </label>

      </div>

      <button type="submit" className="primaryAction" disabled={submitting}>
        {submitting ? "Saving…" : confirmLabel}
      </button>
    </form>
  );
}
