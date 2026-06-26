export type ExperienceLevelValue = "junior" | "mid" | "senior" | "staff";

export type ContentFormatValue =
  | "short_summary"
  | "hands_on"
  | "deep_dive"
  | "quiz"
  | "video"
  | "podcast";

export type DeveloperProfile = {
  name: string | null;
  current_role: string | null;
  experience_years: number | null;
  seniority: ExperienceLevelValue | null;
  current_stack: string[];
  learning: string[];
  domains: string[];
  certifications: string[];
  career_direction: string | null;
  learning_goals: string[];
  topics_to_track: string[];
  topics_to_avoid: string[];
  weekly_time_budget_hours: number;
  preferred_formats: ContentFormatValue[];
  profile_source: "cv" | "linkedin" | "manual" | null;
  raw_text: string | null;
};
