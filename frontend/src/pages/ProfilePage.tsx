// Copyright (c) 2026 Tim Olker
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// SPDX-License-Identifier: Apache-2.0

import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { authService } from "../services/auth";
import {
  userContextService,
  type UserPromptItem,
} from "../services/userContextService";
import { Modal } from "../components/common/Modal";
import {
  User,
  Shield,
  AlertTriangle,
  Trash2,
  Sparkles,
  Compass,
  Heart,
  Clock,
  RotateCcw,
  CheckCircle2,
} from "lucide-react";

export const ProfilePage: React.FC<{ onAccountDeleted: () => void }> = ({
  onAccountDeleted,
}) => {
  const { user } = useAuth();
  const { showToast } = useToast();

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  // Travel style & prompt directives state
  const [travelStyleDescription, setTravelStyleDescription] = useState("");
  const [initialDescription, setInitialDescription] = useState("");
  const [prompts, setPrompts] = useState<UserPromptItem[]>([]);
  const [isLoadingTravelStyle, setIsLoadingTravelStyle] = useState(false);
  const [isSavingTravelStyle, setIsSavingTravelStyle] = useState(false);
  const [isClearingTravelStyle, setIsClearingTravelStyle] = useState(false);

  useEffect(() => {
    if (!user) return;
    setIsLoadingTravelStyle(true);
    userContextService
      .getTravelStyle()
      .then((data) => {
        const desc = data.travel_style_description || "";
        setTravelStyleDescription(desc);
        setInitialDescription(desc);
        setPrompts(data.prompts || []);
      })
      .catch((err) => {
        console.error("Failed to load travel style:", err);
      })
      .finally(() => {
        setIsLoadingTravelStyle(false);
      });
  }, [user?.id]);

  // Support #travel-style anchor scrolling and auto-focus (T-048 / REQ-CTX-011)
  useEffect(() => {
    if (window.location.hash === "#travel-style") {
      const el = document.getElementById("travel-style");
      if (el) {
        setTimeout(() => {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
          const textarea = document.querySelector<HTMLTextAreaElement>(
            "[data-testid='travel-style-textarea']",
          );
          if (textarea) {
            textarea.focus();
          }
        }, 100);
      }
    }
  }, []);

  const handleSaveTravelStyle = async () => {
    setIsSavingTravelStyle(true);
    try {
      const res = await userContextService.updateTravelStyle(
        travelStyleDescription.trim() || null,
      );
      const desc = res.travel_style_description || "";
      setTravelStyleDescription(desc);
      setInitialDescription(desc);
      setPrompts(res.prompts || []);
      showToast("Travel style saved and prompt directives synthesized.", "success");
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(
        errorObj.problem?.detail ||
          errorObj.problem?.title ||
          errorObj.message ||
          "Failed to save travel style.",
        "error",
      );
    } finally {
      setIsSavingTravelStyle(false);
    }
  };

  const handleClearTravelStyle = async () => {
    setIsClearingTravelStyle(true);
    try {
      const res = await userContextService.clearTravelStyle();
      setTravelStyleDescription("");
      setInitialDescription("");
      setPrompts(res.prompts || []);
      showToast(
        "Travel style cleared. Reverted to standard extraction prompts.",
        "info",
      );
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(
        errorObj.problem?.detail ||
          errorObj.problem?.title ||
          errorObj.message ||
          "Failed to clear travel style.",
        "error",
      );
    } finally {
      setIsClearingTravelStyle(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmation !== "DELETE") return;
    setIsDeleting(true);
    try {
      await authService.deleteAccount();
      showToast(
        "Account and all associated tenant data permanently deleted.",
        "info",
      );
      onAccountDeleted();
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(
        errorObj.problem || errorObj.message || "Failed to delete account",
      );
      setIsDeleting(false);
    }
  };

  if (!user) {
    return (
      <div
        style={{
          padding: "40px",
          textAlign: "center",
          color: "var(--text-muted)",
        }}
      >
        Please sign in to view your profile.
      </div>
    );
  }

  const isDirty = travelStyleDescription !== initialDescription;
  const isTooLong = travelStyleDescription.length > 2000;

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "32px 16px" }}>
      <h1 style={{ fontSize: "24px", fontWeight: 800, marginBottom: "24px" }}>
        User Profile
      </h1>

      {/* Identity Card */}
      <div
        style={{
          background: "var(--bg-surface, #ffffff)",
          borderRadius: "var(--radius-lg, 16px)",
          border: "1px solid var(--border-color, #e2e8f0)",
          boxShadow: "var(--shadow-sm)",
          padding: "24px",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
            marginBottom: "16px",
          }}
        >
          <div
            style={{
              width: "54px",
              height: "54px",
              borderRadius: "9999px",
              background: "var(--accent-light, #eff6ff)",
              color: "var(--accent, #2563eb)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <User size={28} />
          </div>
          <div>
            <h2 style={{ fontSize: "18px", fontWeight: 700 }}>
              {user.full_name}
            </h2>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              {user.email}
            </p>
          </div>
          <div style={{ marginLeft: "auto" }}>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 700,
                padding: "4px 10px",
                borderRadius: "9999px",
                background: user.tier === "HIGH" ? "#fef3c7" : "#e0e7ff",
                color: user.tier === "HIGH" ? "#b45309" : "#3730a3",
              }}
            >
              {user.tier} TIER
            </span>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "12px",
            paddingTop: "16px",
            borderTop: "1px solid var(--border-color, #f1f5f9)",
            fontSize: "12px",
          }}
        >
          <div>
            <span style={{ color: "var(--text-muted)" }}>Tenant ID:</span>
            <p style={{ fontFamily: "monospace", fontWeight: 600 }}>
              {user.id}
            </p>
          </div>
          <div>
            <span style={{ color: "var(--text-muted)" }}>Role:</span>
            <p style={{ fontWeight: 600 }}>
              {user.is_admin ? "Platform Administrator" : "Traveler"}
            </p>
          </div>
        </div>
      </div>

      {/* Travel Style & AI Prompt Directives Card (T-018 / REQ-CTX-002, REQ-CTX-007) */}
      <div
        id="travel-style"
        data-testid="travel-style-card"
        style={{
          background: "var(--bg-surface, #ffffff)",
          borderRadius: "var(--radius-lg, 16px)",
          border: "1px solid var(--border-color, #e2e8f0)",
          boxShadow: "var(--shadow-sm)",
          padding: "24px",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "8px",
          }}
        >
          <Sparkles size={20} color="var(--accent, #2563eb)" />
          <h2 style={{ fontSize: "17px", fontWeight: 700, margin: 0 }}>
            Travel Style & AI Context
          </h2>
        </div>
        <p
          style={{
            fontSize: "13px",
            color: "var(--text-secondary)",
            marginBottom: "16px",
            lineHeight: 1.5,
          }}
        >
          Describe what you look for in travel (interests, pace, food passions,
          hidden gems vs. iconic landmarks). Our AI engine extracts modular
          directives to personalize your web captures, itineraries, and durations.
        </p>

        <div style={{ position: "relative", marginBottom: "12px" }}>
          <textarea
            data-testid="travel-style-textarea"
            aria-label="Travel Style Description"
            value={travelStyleDescription}
            onChange={(e) => setTravelStyleDescription(e.target.value)}
            disabled={isLoadingTravelStyle || isSavingTravelStyle}
            placeholder="e.g., I love relaxing vacations exploring local culinary traditions, artisan bakeries, and vibrant food markets. I prefer leisurely pacing with plenty of time to soak in the atmosphere..."
            rows={4}
            style={{
              width: "100%",
              padding: "12px 14px",
              borderRadius: "var(--radius-md, 8px)",
              border: `1px solid ${isTooLong ? "var(--danger, #ef4444)" : "var(--border-color, #cbd5e1)"}`,
              fontSize: "13px",
              fontFamily: "inherit",
              lineHeight: 1.5,
              resize: "vertical",
              outline: "none",
              boxSizing: "border-box",
            }}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              marginTop: "4px",
              fontSize: "11px",
              color: isTooLong ? "var(--danger, #ef4444)" : "var(--text-muted)",
              fontWeight: isTooLong ? 700 : 500,
            }}
          >
            {travelStyleDescription.length} / 2000 characters
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: prompts.length > 0 ? "24px" : "0",
          }}
        >
          <button
            type="button"
            data-testid="save-travel-style-btn"
            disabled={!isDirty || isTooLong || isSavingTravelStyle}
            onClick={handleSaveTravelStyle}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "9px 18px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "13px",
              cursor: !isDirty || isTooLong || isSavingTravelStyle ? "not-allowed" : "pointer",
              opacity: !isDirty || isTooLong || isSavingTravelStyle ? 0.6 : 1,
              border: "none",
            }}
          >
            <CheckCircle2 size={15} />
            <span>
              {isSavingTravelStyle ? "Synthesizing Directives..." : "Save Travel Style"}
            </span>
          </button>

          {(travelStyleDescription || prompts.length > 0) && (
            <button
              type="button"
              data-testid="clear-travel-style-btn"
              disabled={isSavingTravelStyle || isClearingTravelStyle}
              onClick={handleClearTravelStyle}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "9px 16px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--bg-hover, #f1f5f9)",
                color: "var(--text-secondary)",
                fontWeight: 600,
                fontSize: "13px",
                cursor: "pointer",
                border: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              <RotateCcw size={14} />
              <span>{isClearingTravelStyle ? "Clearing..." : "Clear Style"}</span>
            </button>
          )}
        </div>

        {/* Read-Only Synthesized Directives Preview Cards (REQ-CTX-007) */}
        {prompts.length > 0 && (
          <div
            data-testid="prompt-directives-section"
            style={{
              paddingTop: "20px",
              borderTop: "1px solid var(--border-color, #f1f5f9)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginBottom: "12px",
              }}
            >
              <Sparkles size={16} color="var(--accent, #2563eb)" />
              <h3 style={{ fontSize: "14px", fontWeight: 700, margin: 0 }}>
                Active AI Prompt Directives
              </h3>
            </div>
            <p
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginBottom: "14px",
              }}
            >
              These decomposed directives automatically customize your web captures,
              extension highlights, and time spent calculations.
            </p>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: "12px",
              }}
            >
              {prompts.map((p) => {
                let badgeLabel = "Directive";
                let badgeColor = "#2563eb";
                let badgeBg = "#eff6ff";
                let Icon = Compass;

                if (p.prompt_type === "description") {
                  badgeLabel = "Description Focus";
                  badgeColor = "#2563eb";
                  badgeBg = "#eff6ff";
                  Icon = Compass;
                } else if (p.prompt_type === "reason_to_visit") {
                  badgeLabel = "Why Visit Focus";
                  badgeColor = "#7c3aed";
                  badgeBg = "#f5f3ff";
                  Icon = Heart;
                } else if (p.prompt_type === "time_spent") {
                  badgeLabel = "Duration & Pacing";
                  badgeColor = "#059669";
                  badgeBg = "#ecfdf5";
                  Icon = Clock;
                }

                return (
                  <div
                    key={p.prompt_type}
                    data-testid={`prompt-card-${p.prompt_type}`}
                    style={{
                      padding: "14px",
                      borderRadius: "10px",
                      background: "var(--bg-hover, #f8fafc)",
                      border: "1px solid var(--border-color, #e2e8f0)",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "3px 8px",
                          borderRadius: "9999px",
                          background: badgeBg,
                          color: badgeColor,
                          fontSize: "11px",
                          fontWeight: 700,
                          marginBottom: "10px",
                        }}
                      >
                        <Icon size={12} />
                        <span>{badgeLabel}</span>
                      </div>
                      <p
                        style={{
                          fontSize: "12px",
                          color: "var(--text-primary, #1e293b)",
                          lineHeight: 1.5,
                          fontStyle: "italic",
                          margin: "0 0 10px 0",
                        }}
                      >
                        &ldquo;{p.prompt_text}&rdquo;
                      </p>
                    </div>
                    <span
                      style={{
                        fontSize: "10px",
                        color: "var(--text-muted)",
                        marginTop: "auto",
                      }}
                    >
                      Updated: {new Date(p.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Quotas & Usage Card */}
      <div
        style={{
          background: "var(--bg-surface, #ffffff)",
          borderRadius: "var(--radius-lg, 16px)",
          border: "1px solid var(--border-color, #e2e8f0)",
          boxShadow: "var(--shadow-sm)",
          padding: "24px",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: "16px",
          }}
        >
          <Shield size={18} color="var(--accent, #2563eb)" />
          <h3 style={{ fontSize: "16px", fontWeight: 700 }}>
            Quota & Resource Allocation
          </h3>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
          }}
        >
          <div
            style={{
              padding: "14px",
              borderRadius: "8px",
              background: "var(--bg-hover, #f8fafc)",
            }}
          >
            <span
              style={{
                fontSize: "11px",
                color: "var(--text-muted)",
                textTransform: "uppercase",
                fontWeight: 700,
              }}
            >
              Monthly LLM Tokens
            </span>
            <p style={{ fontSize: "20px", fontWeight: 800, marginTop: "4px" }}>
              {user.tier === "HIGH" ? "1,000,000" : "200,000"}
            </p>
            <span
              style={{ fontSize: "11px", color: "var(--success, #10b981)" }}
            >
              Within monthly allocation
            </span>
          </div>

          <div
            style={{
              padding: "14px",
              borderRadius: "8px",
              background: "var(--bg-hover, #f8fafc)",
            }}
          >
            <span
              style={{
                fontSize: "11px",
                color: "var(--text-muted)",
                textTransform: "uppercase",
                fontWeight: 700,
              }}
            >
              Max Ingestion File Size
            </span>
            <p style={{ fontSize: "20px", fontWeight: 800, marginTop: "4px" }}>
              2.0 MB
            </p>
            <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
              Up to 2,000 rows per batch
            </span>
          </div>

          <div
            style={{
              padding: "14px",
              borderRadius: "8px",
              background: "var(--bg-hover, #f8fafc)",
            }}
          >
            <span
              style={{
                fontSize: "11px",
                color: "var(--text-muted)",
                textTransform: "uppercase",
                fontWeight: 700,
              }}
            >
              Duplicate Triage Retention
            </span>
            <p style={{ fontSize: "20px", fontWeight: 800, marginTop: "4px" }}>
              7 Days
            </p>
            <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
              IndexedDB local persistence
            </span>
          </div>
        </div>
      </div>

      {/* Danger Zone: GDPR Account Deletion */}
      <div
        style={{
          background: "var(--bg-surface, #ffffff)",
          borderRadius: "var(--radius-lg, 16px)",
          border: "1px solid #fecaca",
          boxShadow: "var(--shadow-sm)",
          padding: "24px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: "8px",
          }}
        >
          <AlertTriangle size={18} color="var(--danger, #ef4444)" />
          <h3
            style={{
              fontSize: "16px",
              fontWeight: 700,
              color: "var(--danger, #dc2626)",
            }}
          >
            Danger Zone
          </h3>
        </div>
        <p
          style={{
            fontSize: "13px",
            color: "var(--text-secondary)",
            marginBottom: "16px",
          }}
        >
          Cascade account deletion will permanently erase your account, POIs,
          trip lists, and custom preferences in compliance with GDPR. This
          action cannot be reversed.
        </p>

        <button
          type="button"
          onClick={() => setIsDeleteModalOpen(true)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 16px",
            borderRadius: "var(--radius-md, 8px)",
            background: "var(--danger, #ef4444)",
            color: "#ffffff",
            fontWeight: 600,
            fontSize: "13px",
            border: "none",
            cursor: "pointer",
          }}
        >
          <Trash2 size={15} />
          <span>Delete Account</span>
        </button>
      </div>

      {/* Cascade Deletion Confirmation Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Confirm Permanent Deletion"
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <p
            style={{
              fontSize: "13px",
              color: "var(--text-secondary)",
              lineHeight: 1.5,
            }}
          >
            To permanently delete your account and all associated travel
            records, please type <strong>DELETE</strong> below:
          </p>
          <input
            type="text"
            value={deleteConfirmation}
            onChange={(e) => setDeleteConfirmation(e.target.value)}
            placeholder="Type DELETE"
            style={{
              padding: "10px 12px",
              borderRadius: "var(--radius-md, 8px)",
              border: "1px solid var(--border-color, #e2e8f0)",
              fontSize: "14px",
            }}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: "8px",
              marginTop: "8px",
            }}
          >
            <button
              type="button"
              onClick={() => setIsDeleteModalOpen(false)}
              style={{
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--bg-hover, #f1f5f9)",
                color: "var(--text-secondary)",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={deleteConfirmation !== "DELETE" || isDeleting}
              onClick={handleDeleteAccount}
              style={{
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--danger, #ef4444)",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor:
                  deleteConfirmation === "DELETE" ? "pointer" : "not-allowed",
                opacity: deleteConfirmation === "DELETE" ? 1 : 0.6,
              }}
            >
              {isDeleting ? "Deleting..." : "Permanently Delete"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
