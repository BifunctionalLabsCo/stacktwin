"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Archive, CalendarDays, UserCircle } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import {
  setClassroomUserId,
  useActiveClassroomUserId,
  useClassroomUsers
} from "../lib/classroom-user";


export function AppNav() {
  const pathname = usePathname();
  const activeUserId = useActiveClassroomUserId();
  const users = useClassroomUsers();
  const activeUser = users.find((user) => user.id === activeUserId) ?? users[0];

  return (
    <header className="appNav">
      <Link className="appMark" href="/" aria-label="StackTwin current week">
        ST
      </Link>
      <nav aria-label="Classroom navigation">
        <Link href="/" aria-current={pathname === "/" ? "page" : undefined}>
          <CalendarDays size={16} /> Current week
        </Link>
        <Link
          href="/archive/"
          aria-current={pathname.startsWith("/archive") ? "page" : undefined}
        >
          <Archive size={16} /> Archive
        </Link>
        <Link
          href="/profile/"
          aria-current={pathname.startsWith("/profile") ? "page" : undefined}
        >
          <UserCircle size={16} /> Profile
        </Link>
      </nav>
      <div className="appNavActions">
        <label className="userSwitcher" htmlFor="classroom-user-switcher">
          <span>Active learner</span>
          <select
            id="classroom-user-switcher"
            value={activeUser?.id ?? ""}
            onChange={(event) => setClassroomUserId(event.target.value)}
            aria-label="Switch active learner"
          >
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.label} ({user.id})
              </option>
            ))}
          </select>
        </label>
        <ThemeToggle />
      </div>
    </header>
  );
}
