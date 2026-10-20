// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React from "react";
import { ThemeSwitcher } from "./ThemeSwitcher";
import {
  Compass,
  PlusCircle,
  UploadCloud,
  Settings,
  Shield,
  User,
  LogOut,
  FileText,
} from "lucide-react";

export interface NavbarProps {
  currentView: string;
  onNavigate: (view: string) => void;
  user?: {
    id: string;
    email: string;
    full_name: string;
    is_admin: boolean;
    tier?: string;
  } | null;
  onOpenAddPOI?: () => void;
  onOpenUploadCSV?: () => void;
  onLogout?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentView,
  onNavigate,
  user,
  onOpenAddPOI,
  onOpenUploadCSV,
  onLogout,
}) => {
  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 24px",
        background: "var(--bg-surface, #ffffff)",
        borderBottom: "1px solid var(--border-color, #e2e8f0)",
        zIndex: 50,
      }}
    >
      {/* Brand */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          cursor: "pointer",
        }}
        onClick={() => onNavigate("home")}
      >
        <span style={{ fontSize: "22px" }}>🧭</span>
        <span
          style={{
            fontSize: "18px",
            fontWeight: 800,
            letterSpacing: "-0.02em",
          }}
        >
          Vistarae
        </span>
      </div>

      {/* Navigation Links */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        {user ? (
          <>
            <button
              type="button"
              onClick={() => onNavigate("home")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "var(--radius-md, 8px)",
                background:
                  currentView === "home"
                    ? "var(--accent-light, #eff6ff)"
                    : "transparent",
                color:
                  currentView === "home"
                    ? "var(--accent, #2563eb)"
                    : "var(--text-secondary, #475569)",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              <Compass size={15} />
              <span>Explorer</span>
            </button>

            {onOpenAddPOI && (
              <button
                type="button"
                onClick={onOpenAddPOI}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 12px",
                  borderRadius: "var(--radius-md, 8px)",
                  background: "transparent",
                  color: "var(--text-secondary, #475569)",
                  fontSize: "13px",
                  fontWeight: 600,
                }}
              >
                <PlusCircle size={15} />
                <span>Add POI</span>
              </button>
            )}

            {onOpenUploadCSV && (
              <button
                type="button"
                onClick={onOpenUploadCSV}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 12px",
                  borderRadius: "var(--radius-md, 8px)",
                  background: "transparent",
                  color: "var(--text-secondary, #475569)",
                  fontSize: "13px",
                  fontWeight: 600,
                }}
              >
                <UploadCloud size={15} />
                <span>Import CSV</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => onNavigate("settings")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "var(--radius-md, 8px)",
                background: currentView.startsWith("settings")
                  ? "var(--accent-light, #eff6ff)"
                  : "transparent",
                color: currentView.startsWith("settings")
                  ? "var(--accent, #2563eb)"
                  : "var(--text-secondary, #475569)",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              <Settings size={15} />
              <span>Preferences</span>
            </button>

            {user?.is_admin && (
              <button
                type="button"
                onClick={() => onNavigate("admin")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 12px",
                  borderRadius: "var(--radius-md, 8px)",
                  background:
                    currentView === "admin"
                      ? "var(--accent-light, #eff6ff)"
                      : "transparent",
                  color:
                    currentView === "admin"
                      ? "var(--accent, #2563eb)"
                      : "var(--text-secondary, #475569)",
                  fontSize: "13px",
                  fontWeight: 600,
                }}
              >
                <Shield size={15} />
                <span>Admin</span>
              </button>
            )}
          </>
        ) : (
          <button
            type="button"
            onClick={() => {
              onNavigate("home");
              setTimeout(() => {
                const el = document.getElementById("features");
                if (el) el.scrollIntoView({ behavior: "smooth" });
              }, 50);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "var(--radius-md, 8px)",
              background: "transparent",
              color: "var(--text-secondary, #475569)",
              fontSize: "13px",
              fontWeight: 600,
            }}
          >
            <Compass size={15} />
            <span>Features</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => onNavigate("terms")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 12px",
            borderRadius: "var(--radius-md, 8px)",
            background:
              currentView === "terms"
                ? "var(--accent-light, #eff6ff)"
                : "transparent",
            color:
              currentView === "terms"
                ? "var(--accent, #2563eb)"
                : "var(--text-secondary, #475569)",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          <FileText size={15} />
          <span>Terms</span>
        </button>
      </div>

      {/* Right controls: ThemeSwitcher & Profile */}
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        <ThemeSwitcher />

        {user ? (
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button
              type="button"
              onClick={() => onNavigate("profile")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "4px 10px",
                borderRadius: "var(--radius-md, 8px)",
                background:
                  currentView === "profile"
                    ? "var(--accent-light, #eff6ff)"
                    : "var(--bg-hover, #f1f5f9)",
                color: "var(--text-primary)",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              <User size={15} />
              <span>{user.full_name || user.email}</span>
              {user.tier && (
                <span
                  style={{
                    fontSize: "10px",
                    padding: "1px 5px",
                    borderRadius: "4px",
                    background: user.tier === "HIGH" ? "#fef3c7" : "#e0e7ff",
                    color: user.tier === "HIGH" ? "#b45309" : "#3730a3",
                    fontWeight: 700,
                  }}
                >
                  {user.tier}
                </span>
              )}
            </button>

            {onLogout && (
              <button
                type="button"
                onClick={onLogout}
                title="Log out"
                style={{
                  padding: "6px",
                  borderRadius: "var(--radius-sm, 6px)",
                  color: "var(--text-muted)",
                }}
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <button
              type="button"
              onClick={() => onNavigate("login")}
              style={{
                padding: "6px 14px",
                borderRadius: "var(--radius-md, 8px)",
                background: "transparent",
                color: "var(--text-primary)",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => onNavigate("signup")}
              style={{
                padding: "6px 14px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--accent, #2563eb)",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              Sign Up
            </button>
          </div>
        )}
      </div>
    </nav>
  );
};
