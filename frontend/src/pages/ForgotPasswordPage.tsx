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

// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState } from "react";
import { authService } from "../services/auth";
import { useToast } from "../context/ToastContext";
import { Mail, ArrowRight, ArrowLeft } from "lucide-react";

interface ForgotPasswordPageProps {
  onCodeSent: (email: string) => void;
  onNavigateLogin: () => void;
}

export const ForgotPasswordPage: React.FC<ForgotPasswordPageProps> = ({
  onCodeSent,
  onNavigateLogin,
}) => {
  const { showToast } = useToast();
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setIsSubmitting(true);
    try {
      await authService.forgotPassword(email);
      showToast("Password recovery code sent to your email!", "info");
      onCodeSent(email);
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(
        errorObj.problem || errorObj.message || "Could not send recovery code",
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
        <button
          type="button"
          onClick={onNavigateLogin}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            fontSize: "12px",
            color: "var(--text-muted)",
            marginBottom: "16px",
          }}
        >
          <ArrowLeft size={14} />
          <span>Back to sign in</span>
        </button>

        <h2 style={{ fontSize: "20px", fontWeight: 800, marginBottom: "6px" }}>
          Reset Password
        </h2>
        <p
          style={{
            fontSize: "13px",
            color: "var(--text-muted)",
            marginBottom: "24px",
          }}
        >
          Enter the email associated with your Vistarae account and we'll send
          you a recovery code.
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
              Email Address
            </label>
            <div style={{ position: "relative" }}>
              <Mail
                size={16}
                color="var(--text-muted)"
                style={{ position: "absolute", left: "12px", top: "12px" }}
              />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="traveler@example.com"
                style={{
                  width: "100%",
                  padding: "10px 12px 10px 38px",
                  borderRadius: "var(--radius-md, 8px)",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                  fontSize: "13px",
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
              {isSubmitting ? "Sending Code..." : "Send Recovery Code"}
            </span>
            <ArrowRight size={16} />
          </button>
        </form>
      </div>
    </div>
  );
};
