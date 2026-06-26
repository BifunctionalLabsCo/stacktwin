"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Archive, CalendarDays, UserCircle } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";


export function AppNav() {
  const pathname = usePathname();

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
      <ThemeToggle />
    </header>
  );
}
