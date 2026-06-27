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
const CHANGE_EVENT = "stacktwin-user-change";

const CLASSROOM_USERS = parseConfiguredClassroomUsers(process.env.NEXT_PUBLIC_STACKTWIN_DEMO_USERS);
const DEFAULT_USERS = getDefaultClassroomUsers();
const DEFAULT_USER_ID = CLASSROOM_USERS[0]?.id ?? DEFAULT_USERS[0].id;

function readStoredUserId() {
  if (typeof window === "undefined") {
    return DEFAULT_USER_ID;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  return normalizeClassroomUserId(stored, CLASSROOM_USERS);
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
  return CLASSROOM_USERS;
}

export function getClassroomUserId() {
  return readStoredUserId();
}

export function getClassroomUserLabel(userId: string) {
  return getClassroomUsers().find((user) => user.id === userId)?.label ?? formatUserLabel(userId);
}

export function setClassroomUserId(userId: string) {
  const nextUserId = normalizeClassroomUserId(userId, CLASSROOM_USERS);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, nextUserId);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }
  return nextUserId;
}

export function useClassroomUsers() {
  return CLASSROOM_USERS;
}

export function useActiveClassroomUserId() {
  return useSyncExternalStore(subscribe, readStoredUserId, () => DEFAULT_USER_ID);
}
