// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertOctagon, RotateCw, Home } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(
      "Unhandled React Render Error in ErrorBoundary:",
      error,
      errorInfo,
    );
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = "/";
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            padding: "24px",
            background: "var(--bg-primary, #f8fafc)",
            color: "var(--text-primary, #0f172a)",
            textAlign: "center",
          }}
        >
          <div
            style={{
              maxWidth: "480px",
              padding: "32px",
              background: "var(--bg-surface, #ffffff)",
              borderRadius: "var(--radius-lg, 16px)",
              boxShadow: "var(--shadow-lg)",
              border: "1px solid var(--border-color, #e2e8f0)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "16px",
            }}
          >
            <AlertOctagon size={44} color="var(--danger, #ef4444)" />
            <h2 style={{ fontSize: "20px", fontWeight: 800 }}>
              Something went wrong
            </h2>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary, #475569)",
                lineHeight: 1.5,
              }}
            >
              The application encountered an unexpected runtime error. We've
              preserved your local state and logged the incident.
            </p>

            {this.state.error && (
              <pre
                style={{
                  width: "100%",
                  padding: "10px",
                  background: "var(--bg-hover, #f1f5f9)",
                  color: "var(--danger, #b91c1c)",
                  borderRadius: "var(--radius-sm, 6px)",
                  fontSize: "11px",
                  overflowX: "auto",
                  textAlign: "left",
                }}
              >
                {this.state.error.message}
              </pre>
            )}

            <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
              <button
                type="button"
                onClick={this.handleReload}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "8px 16px",
                  borderRadius: "var(--radius-md, 8px)",
                  background: "var(--accent, #2563eb)",
                  color: "#ffffff",
                  fontWeight: 600,
                  fontSize: "13px",
                }}
              >
                <RotateCw size={14} />
                <span>Reload Page</span>
              </button>
              <button
                type="button"
                onClick={this.handleGoHome}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "8px 16px",
                  borderRadius: "var(--radius-md, 8px)",
                  background: "var(--bg-hover, #f1f5f9)",
                  color: "var(--text-secondary, #475569)",
                  fontWeight: 600,
                  fontSize: "13px",
                  border: "1px solid var(--border-color, #e2e8f0)",
                }}
              >
                <Home size={14} />
                <span>Return to Safety</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
