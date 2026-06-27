"use client";

import { useEffect, useId, useState } from "react";
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

export function QuickStartProfileForm({
  profile,
  onConfirm,
  onExpandFullProfile,
  submitting,
  confirmLabel
}: {
  profile: DeveloperProfile;
  onConfirm: (profile: DeveloperProfile) => void;
  onExpandFullProfile: (profile: DeveloperProfile) => void;
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
      className="quickStartForm"
      aria-label="Quick start profile setup"
      onSubmit={(event) => {
        event.preventDefault();
        onConfirm(draft);
      }}
    >
      <div className="quickStartIntro">
        <p className="eyebrow">Quick start</p>
        <h2>Seed a useful profile in under a minute</h2>
        <p>
          Add only the fields that matter for the first classroom pass. You can expand the rest
          later from the full review surface.
        </p>
      </div>

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

      <div className="quickStartActions">
        <button type="submit" className="primaryAction" disabled={submitting}>
          {submitting ? "Saving…" : confirmLabel}
        </button>
        <button
          type="button"
          className="secondaryAction"
          onClick={() => onExpandFullProfile(draft)}
        >
          Open full review
        </button>
      </div>
    </form>
  );
}
