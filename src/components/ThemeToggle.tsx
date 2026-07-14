"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type Theme = "system" | "light" | "dark";

const THEMES: { value: Theme; Icon: typeof Sun; label: string }[] = [
  { value: "system", Icon: Monitor, label: "System" },
  { value: "light", Icon: Sun, label: "Light" },
  { value: "dark", Icon: Moon, label: "Dark" }
];

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    const stored = (localStorage.getItem("theme") as Theme) ?? "system";
    setTheme(stored);
    applyTheme(stored);
  }, []);

  function select(next: Theme) {
    setTheme(next);
    localStorage.setItem("theme", next);
    applyTheme(next);
  }

  return (
    <div className="themeToggle" role="group" aria-label="Color theme">
      {THEMES.map(({ value, Icon, label }) => (
        <button
          key={value}
          type="button"
          aria-label={label}
          title={`${label} theme`}
          aria-pressed={theme === value}
          onClick={() => select(value)}
        >
          <Icon size={14} />
        </button>
      ))}
    </div>
  );
}
