// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useState } from "react";
import { useToast, type ToastItem } from "../../context/ToastContext";
import {
  AlertCircle,
  CheckCircle,
  Info,
  AlertTriangle,
  X,
  Clock,
} from "lucide-react";

const ToastRow: React.FC<{ toast: ToastItem; onDismiss: () => void }> = ({
  toast,
  onDismiss,
}) => {
  const [countdown, setCountdown] = useState<number | undefined>(
    toast.retryAfterSeconds,
  );

  // Auto-dismiss countdown for durationMs
  useEffect(() => {
    if (!toast.durationMs) return;
    const timer = setTimeout(onDismiss, toast.durationMs);
    return () => clearTimeout(timer);
  }, [toast.durationMs, onDismiss]);

  // Rate-limiting countdown timer for HTTP 429 Retry-After
  useEffect(() => {
    if (countdown === undefined || countdown <= 0) return;
    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev === undefined || prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [countdown]);

  const getIcon = () => {
    switch (toast.type) {
      case "success":
        return <CheckCircle size={18} color="var(--success, #10b981)" />;
      case "warning":
        return <AlertTriangle size={18} color="var(--warning, #f59e0b)" />;
      case "info":
        return <Info size={18} color="var(--info, #0284c7)" />;
      default:
        return <AlertCircle size={18} color="var(--danger, #ef4444)" />;
    }
  };

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="toast-card slide-up"
      style={{
        display: "flex",
        flexDirection: "column",
        width: "360px",
        maxWidth: "90vw",
        padding: "12px 14px",
        background: "var(--bg-surface, #ffffff)",
        color: "var(--text-primary, #0f172a)",
        borderRadius: "var(--radius-md, 8px)",
        boxShadow: "var(--shadow-lg)",
        borderLeft: `4px solid ${
          toast.type === "success"
            ? "var(--success, #10b981)"
            : toast.type === "warning"
              ? "var(--warning, #f59e0b)"
              : toast.type === "info"
                ? "var(--info, #0284c7)"
                : "var(--danger, #ef4444)"
        }`,
        borderTop: "1px solid var(--border-color, #e2e8f0)",
        borderRight: "1px solid var(--border-color, #e2e8f0)",
        borderBottom: "1px solid var(--border-color, #e2e8f0)",
        pointerEvents: "auto",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {getIcon()}
          <strong style={{ fontSize: "13px" }}>{toast.title}</strong>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          style={{ padding: "2px", color: "var(--text-muted)" }}
          aria-label="Close notification"
        >
          <X size={15} />
        </button>
      </div>

      <p
        style={{
          fontSize: "12px",
          color: "var(--text-secondary, #475569)",
          marginTop: "4px",
          marginLeft: "26px",
        }}
      >
        {toast.detail}
      </p>

      {/* Real-time countdown for HTTP 429 */}
      {countdown !== undefined && countdown > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            marginTop: "8px",
            marginLeft: "26px",
            padding: "4px 8px",
            borderRadius: "4px",
            background: "var(--bg-hover, #f1f5f9)",
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--warning, #b45309)",
          }}
        >
          <Clock size={13} />
          <span>Rate limit window resets in {countdown}s</span>
        </div>
      )}

      {/* Field-level validation parameter hints */}
      {toast.invalidParams && toast.invalidParams.length > 0 && (
        <ul
          style={{
            marginTop: "6px",
            marginLeft: "36px",
            fontSize: "11px",
            color: "var(--danger, #dc2626)",
            listStyleType: "disc",
          }}
        >
          {toast.invalidParams.map((param) => (
            <li key={param.name}>
              <strong>{param.name}</strong>: {param.reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export const ToastBanner: React.FC = () => {
  const { toasts, dismissToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      className="toast-banner-container"
      style={{
        position: "fixed",
        bottom: "24px",
        right: "24px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        zIndex: 9999,
        pointerEvents: "none",
      }}
    >
      {toasts.map((toast) => (
        <ToastRow
          key={toast.id}
          toast={toast}
          onDismiss={() => dismissToast(toast.id)}
        />
      ))}
    </div>
  );
};
