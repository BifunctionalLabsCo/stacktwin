"use client";

import { useSyncExternalStore } from "react";
import {
  formatUserLabel,
  getDefaultClassroomUsers,
  normalizeClassroomUserId,
  parseConfiguredClassroomUsers,
  type ClassroomUser
} from "./classroom-user-data";

const STORAGE_KEY = "stacktwin.active-user-id";
const CUSTOM_USERS_STORAGE_KEY = "stacktwin.custom-users";
const CHANGE_EVENT = "stacktwin-user-change";

const CLASSROOM_USERS = parseConfiguredClassroomUsers(process.env.NEXT_PUBLIC_STACKTWIN_DEMO_USERS);
const DEFAULT_USERS = getDefaultClassroomUsers();
const DEFAULT_USER_ID = CLASSROOM_USERS[0]?.id ?? DEFAULT_USERS[0].id;
let cachedCustomUsers = "";
let cachedUsers = CLASSROOM_USERS;

function readClassroomUsers() {
  if (typeof window === "undefined") {
    return CLASSROOM_USERS;
  }

  const serialized = window.localStorage.getItem(CUSTOM_USERS_STORAGE_KEY) ?? "";
  if (serialized === cachedCustomUsers) {
    return cachedUsers;
  }

  cachedCustomUsers = serialized;
  cachedUsers = [...CLASSROOM_USERS, ...parseConfiguredClassroomUsers(serialized).filter(
    (candidate) => !CLASSROOM_USERS.some((user) => user.id === candidate.id)
  )];
  return cachedUsers;
}

function readStoredUserId() {
  if (typeof window === "undefined") {
    return DEFAULT_USER_ID;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  return normalizeClassroomUserId(stored, readClassroomUsers());
}

function subscribe(listener: () => void) {
  if (typeof window === "undefined") {
    return () => {};
  }

  const handleStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY || event.key === null) {
      listener();
    }
  };

  window.addEventListener(CHANGE_EVENT, listener);
  window.addEventListener("storage", handleStorage);
  return () => {
    window.removeEventListener(CHANGE_EVENT, listener);
    window.removeEventListener("storage", handleStorage);
  };
}

export type { ClassroomUser };

export function getClassroomUsers() {
  return readClassroomUsers();
}

export function getClassroomUserId() {
  return readStoredUserId();
}

export function getClassroomUserLabel(userId: string) {
  return getClassroomUsers().find((user) => user.id === userId)?.label ?? formatUserLabel(userId);
}

export function setClassroomUserId(userId: string) {
  const nextUserId = normalizeClassroomUserId(userId, getClassroomUsers());
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, nextUserId);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }
  return nextUserId;
}

export function createClassroomUser() {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : String(Date.now());
  const user: ClassroomUser = {
    id: `profile-${suffix}@stacktwin.local`,
    label: "New profile",
    description: "Personalized learning profile"
  };

  if (typeof window !== "undefined") {
    const customUsers = parseConfiguredClassroomUsers(
      window.localStorage.getItem(CUSTOM_USERS_STORAGE_KEY) ?? ""
    );
    window.localStorage.setItem(CUSTOM_USERS_STORAGE_KEY, JSON.stringify([...customUsers, user]));
    cachedCustomUsers = "";
    setClassroomUserId(user.id);
  }

  return user;
}

export function useClassroomUsers() {
  return useSyncExternalStore(subscribe, getClassroomUsers, () => CLASSROOM_USERS);
}

export function useActiveClassroomUserId() {
  return useSyncExternalStore(subscribe, readStoredUserId, () => DEFAULT_USER_ID);
}
