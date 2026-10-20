// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React from "react";
import { useTheme, type ThemeMode } from "../../context/ThemeContext";
import { Sun, Moon, Laptop } from "lucide-react";

export const ThemeSwitcher: React.FC = () => {
  const { theme, setTheme } = useTheme();

  const options: Array<{
    mode: ThemeMode;
    label: string;
    icon: React.ReactNode;
  }> = [
    { mode: "light", label: "Light", icon: <Sun size={14} /> },
    { mode: "dark", label: "Dark", icon: <Moon size={14} /> },
    { mode: "system", label: "System", icon: <Laptop size={14} /> },
  ];

  return (
    <div
      className="theme-switcher-group"
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px",
        borderRadius: "var(--radius-full, 9999px)",
        background: "var(--bg-hover, #f1f5f9)",
        border: "1px solid var(--border-color, #e2e8f0)",
      }}
    >
      {options.map((opt) => {
        const isActive = theme === opt.mode;
        return (
          <button
            key={opt.mode}
            type="button"
            onClick={() => setTheme(opt.mode)}
            title={`Switch to ${opt.label} mode`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: "4px 10px",
              borderRadius: "var(--radius-full, 9999px)",
              background: isActive
                ? "var(--bg-surface, #ffffff)"
                : "transparent",
              color: isActive
                ? "var(--accent, #2563eb)"
                : "var(--text-secondary, #64748b)",
              fontSize: "12px",
              fontWeight: isActive ? 600 : 500,
              boxShadow: isActive ? "var(--shadow-sm)" : "none",
              transition: "all var(--transition-fast)",
            }}
          >
            {opt.icon}
            <span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
};
