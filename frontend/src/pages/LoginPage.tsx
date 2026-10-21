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
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Lock, Mail, ArrowRight } from "lucide-react";

interface LoginPageProps {
  onSuccess: () => void;
  onNavigateSignUp: () => void;
  onNavigateForgotPassword: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({
  onSuccess,
  onNavigateSignUp,
  onNavigateForgotPassword,
}) => {
  const { login } = useAuth();
  const { showToast } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;

    setIsSubmitting(true);
    try {
      await login(email, password);
      showToast("Successfully signed in!", "success");
      onSuccess();
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(
        errorObj.problem || errorObj.message || "Authentication failed",
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
        <div style={{ textAlign: "center", marginBottom: "28px" }}>
          <span style={{ fontSize: "32px" }}>🧭</span>
          <h2 style={{ fontSize: "22px", fontWeight: 800, marginTop: "8px" }}>
            Sign in to Vistarae
          </h2>
          <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            Access your captured travel POIs and custom map views
          </p>
        </div>

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

          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "6px",
              }}
            >
              <label style={{ fontSize: "12px", fontWeight: 600 }}>
                Password
              </label>
              <button
                type="button"
                onClick={onNavigateForgotPassword}
                style={{
                  fontSize: "12px",
                  color: "var(--accent, #2563eb)",
                  fontWeight: 500,
                }}
              >
                Forgot password?
              </button>
            </div>
            <div style={{ position: "relative" }}>
              <Lock
                size={16}
                color="var(--text-muted)"
                style={{ position: "absolute", left: "12px", top: "12px" }}
              />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
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
              marginTop: "8px",
              cursor: isSubmitting ? "not-allowed" : "pointer",
              opacity: isSubmitting ? 0.7 : 1,
            }}
          >
            <span>{isSubmitting ? "Authenticating..." : "Sign In"}</span>
            <ArrowRight size={16} />
          </button>
        </form>

        <div
          style={{ textAlign: "center", marginTop: "24px", fontSize: "13px" }}
        >
          <span style={{ color: "var(--text-secondary)" }}>
            Don't have an account?{" "}
          </span>
          <button
            type="button"
            onClick={onNavigateSignUp}
            style={{ color: "var(--accent, #2563eb)", fontWeight: 600 }}
          >
            Create an account
          </button>
        </div>
      </div>
    </div>
  );
};
