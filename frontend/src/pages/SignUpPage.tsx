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
import { Mail, Lock, User, KeyRound, ArrowRight } from "lucide-react";

interface SignUpPageProps {
  onSuccess: () => void;
  onNavigateLogin: () => void;
}

export const SignUpPage: React.FC<SignUpPageProps> = ({
  onSuccess,
  onNavigateLogin,
}) => {
  const { showToast } = useToast();

  const [step, setStep] = useState<"REGISTER" | "CONFIRM">("REGISTER");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || !fullName) return;

    setIsSubmitting(true);
    try {
      await authService.register(email, password, fullName);
      const isLocal =
        typeof window !== "undefined" &&
        (window.location.hostname === "localhost" ||
          window.location.hostname === "127.0.0.1");
      showToast(
        isLocal
          ? "Local dev mode: No email sent. Enter 123456 to verify."
          : "Confirmation code sent to your email!",
        "info",
      );
      setStep("CONFIRM");
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(errorObj.problem || errorObj.message || "Registration failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code) return;

    setIsSubmitting(true);
    try {
      await authService.confirmSignUp(email, code);
      showToast("Account verified! You can now sign in.", "success");
      onSuccess();
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(errorObj.problem || errorObj.message || "Verification failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const isLocalEnv =
    typeof window !== "undefined" &&
    (window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1");

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
            {step === "REGISTER"
              ? "Create your Account"
              : "Verify Email Address"}
          </h2>
          <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            {step === "REGISTER"
              ? "Start capturing scenic overlooks, trails, and travel dreams"
              : isLocalEnv
                ? "Local dev mode active — enter verification code below"
                : `Enter the 6-digit confirmation code sent to ${email}`}
          </p>
        </div>

        {step === "REGISTER" ? (
          <form
            onSubmit={handleRegister}
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
                Full Name
              </label>
              <div style={{ position: "relative" }}>
                <User
                  size={16}
                  color="var(--text-muted)"
                  style={{ position: "absolute", left: "12px", top: "12px" }}
                />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Traveler"
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
              <label
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  display: "block",
                  marginBottom: "6px",
                }}
              >
                Password (min 8 characters)
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
              }}
            >
              <span>{isSubmitting ? "Creating Account..." : "Continue"}</span>
              <ArrowRight size={16} />
            </button>
          </form>
        ) : (
          <form
            onSubmit={handleConfirm}
            style={{ display: "flex", flexDirection: "column", gap: "16px" }}
          >
            {isLocalEnv && (
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "8px",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md, 8px)",
                  background: "rgba(37, 99, 235, 0.08)",
                  border: "1px solid rgba(37, 99, 235, 0.2)",
                  fontSize: "12px",
                  color: "var(--text-secondary)",
                  lineHeight: "1.4",
                }}
              >
                <span style={{ fontSize: "14px" }}>💡</span>
                <div>
                  <strong style={{ color: "var(--accent, #2563eb)" }}>
                    Local Dev Mode:
                  </strong>{" "}
                  No external email provider is configured. Enter{" "}
                  <code
                    style={{
                      fontWeight: 700,
                      color: "var(--accent, #2563eb)",
                      background: "rgba(37, 99, 235, 0.12)",
                      padding: "1px 4px",
                      borderRadius: "4px",
                    }}
                  >
                    123456
                  </code>{" "}
                  (or any 6 digits) to activate your account.
                </div>
              </div>
            )}

            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "6px",
                }}
              >
                <label
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                  }}
                >
                  Confirmation Code
                </label>
                {isLocalEnv && (
                  <button
                    type="button"
                    onClick={() => setCode("123456")}
                    style={{
                      fontSize: "11px",
                      color: "var(--accent, #2563eb)",
                      fontWeight: 600,
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: 0,
                    }}
                  >
                    Auto-fill 123456
                  </button>
                )}
              </div>
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
                    fontSize: "16px",
                    letterSpacing: "4px",
                    textAlign: "center",
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
              }}
            >
              <span>{isSubmitting ? "Verifying..." : "Verify & Complete"}</span>
              <ArrowRight size={16} />
            </button>
          </form>
        )}

        <div
          style={{ textAlign: "center", marginTop: "24px", fontSize: "13px" }}
        >
          <span style={{ color: "var(--text-secondary)" }}>
            Already have an account?{" "}
          </span>
          <button
            type="button"
            onClick={onNavigateLogin}
            style={{ color: "var(--accent, #2563eb)", fontWeight: 600 }}
          >
            Sign in
          </button>
        </div>
      </div>
    </div>
  );
};
