export type ClassroomUser = {
  id: string;
  label: string;
  description?: string;
};

const FALLBACK_USERS: ClassroomUser[] = [
  { id: "engineer@stacktwin.dev", label: "Engineer", description: "Systems, tooling, and product engineering" },
  { id: "creator@stacktwin.dev", label: "Creator", description: "Ideas, storytelling, and product craft" },
  { id: "researcher@stacktwin.dev", label: "Researcher", description: "Evidence, emerging technology, and insight" }
];

export function getDefaultClassroomUsers() {
  return FALLBACK_USERS;
}

export function parseConfiguredClassroomUsers(rawValue: string | undefined): ClassroomUser[] {
  if (!rawValue) {
    return FALLBACK_USERS;
  }

  try {
    const parsed = JSON.parse(rawValue) as unknown;
    const normalized = normalizeUsers(parsed);
    if (normalized.length > 0) {
      return normalized;
    }
  } catch {
    // Fall back to the simpler comma-separated format below.
  }

  const normalized = rawValue
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [idPart, labelPart, descriptionPart] = entry.split("|").map((part) => part.trim());
      if (!idPart) {
        return null;
      }
      const user: ClassroomUser = {
        id: idPart,
        label: labelPart || formatUserLabel(idPart),
        ...(descriptionPart ? { description: descriptionPart } : {})
      };
      return user;
    })
    .filter((entry): entry is ClassroomUser => entry !== null);

  return normalized.length > 0 ? normalized : FALLBACK_USERS;
}

export function normalizeClassroomUserId(userId: string | null | undefined, users = FALLBACK_USERS) {
  const candidate = typeof userId === "string" ? userId.trim() : "";
  if (!candidate) {
    return users[0]?.id ?? FALLBACK_USERS[0].id;
  }
  return users.some((user) => user.id === candidate) ? candidate : users[0]?.id ?? FALLBACK_USERS[0].id;
}

export function formatUserLabel(userId: string) {
  const localPart = userId.split("@")[0] ?? userId;
  const normalized = localPart.replace(/[._-]+/g, " ").trim();
  return normalized ? normalized.replace(/\b\w/g, (char) => char.toUpperCase()) : userId;
}

function normalizeUsers(value: unknown): ClassroomUser[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((entry) => {
      if (typeof entry === "string") {
        const user: ClassroomUser = { id: entry.trim(), label: formatUserLabel(entry) };
        return user;
      }
      if (!entry || typeof entry !== "object") {
        return null;
      }

      const candidate = entry as Partial<ClassroomUser> & { name?: string };
      const id = typeof candidate.id === "string" ? candidate.id.trim() : "";
      if (!id) {
        return null;
      }

      const user: ClassroomUser = {
        id,
        label:
          typeof candidate.label === "string" && candidate.label.trim()
            ? candidate.label.trim()
            : typeof candidate.name === "string" && candidate.name.trim()
              ? candidate.name.trim()
              : formatUserLabel(id),
        ...(typeof candidate.description === "string" && candidate.description.trim()
          ? { description: candidate.description.trim() }
          : {})
      };
      return user;
    })
    .filter((entry): entry is ClassroomUser => entry !== null);
}
