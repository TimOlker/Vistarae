// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { authService } from "../services/auth";
import { Modal } from "../components/common/Modal";
import { User, Shield, AlertTriangle, Trash2 } from "lucide-react";

export const ProfilePage: React.FC<{ onAccountDeleted: () => void }> = ({
  onAccountDeleted,
}) => {
  const { user } = useAuth();
  const { showToast } = useToast();

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

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
