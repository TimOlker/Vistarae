// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState } from "react";
import { authService } from "../services/auth";
import { useToast } from "../context/ToastContext";
import { KeyRound, Lock, ArrowRight } from "lucide-react";

interface ResetPasswordPageProps {
  email: string;
  onSuccess: () => void;
}

export const ResetPasswordPage: React.FC<ResetPasswordPageProps> = ({
  email,
  onSuccess,
}) => {
  const { showToast } = useToast();
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code || !newPassword) return;

    setIsSubmitting(true);
    try {
      await authService.resetPassword(email, code, newPassword);
      showToast(
        "Password reset successfully! Please sign in with your new password.",
        "success",
      );
      onSuccess();
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(
        errorObj.problem || errorObj.message || "Password reset failed",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "var(--bg-primary, #f8fafc)",
        padding: "20px",
      }}
    >
      <div
        className="slide-up"
        style={{
          width: "100%",
          maxWidth: "420px",
          background: "var(--bg-surface, #ffffff)",
          borderRadius: "var(--radius-lg, 16px)",
          boxShadow: "var(--shadow-lg)",
          border: "1px solid var(--border-color, #e2e8f0)",
          padding: "36px",
        }}
      >
        <h2 style={{ fontSize: "20px", fontWeight: 800, marginBottom: "6px" }}>
          Enter New Password
        </h2>
        <p
          style={{
            fontSize: "13px",
            color: "var(--text-muted)",
            marginBottom: "24px",
          }}
        >
          Enter the recovery code sent to <strong>{email}</strong> and your new
          password.
        </p>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: "16px" }}
        >
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 600,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Recovery Code
            </label>
            <div style={{ position: "relative" }}>
              <KeyRound
                size={16}
                color="var(--text-muted)"
                style={{ position: "absolute", left: "12px", top: "12px" }}
              />
              <input
                type="text"
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="123456"
                style={{
                  width: "100%",
                  padding: "10px 12px 10px 38px",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                  fontSize: "14px",
                }}
              />
            </div>
          </div>

          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 600,
                display: "block",
                marginBottom: "6px",
              }}
            >
              New Password
            </label>
            <div style={{ position: "relative" }}>
              <Lock
                size={16}
                color="var(--text-muted)"
                style={{ position: "absolute", left: "12px", top: "12px" }}
              />
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••••••"
                style={{
                  width: "100%",
                  padding: "10px 12px 10px 38px",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                  fontSize: "14px",
                }}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "12px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "14px",
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
          >
            <span>
              {isSubmitting ? "Resetting Password..." : "Save New Password"}
            </span>
            <ArrowRight size={16} />
          </button>
        </form>
      </div>
    </div>
  );
};
