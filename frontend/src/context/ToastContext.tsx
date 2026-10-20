// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { createContext, useContext, useState, useCallback } from "react";
import type { ProblemDetails } from "../services/api";

export type ToastType = "error" | "success" | "info" | "warning";

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  detail: string;
  invalidParams?: Array<{ name: string; reason: string }>;
  retryAfterSeconds?: number;
  durationMs?: number;
}

export type ToastInput =
  | ProblemDetails
  | {
      title?: string;
      detail?: string;
      status?: number;
      invalid_params?: Array<{ name: string; reason: string }>;
      retryAfterSeconds?: number;
    }
  | string;

interface ToastContextValue {
  toasts: ToastItem[];
  showToast: (problemOrMsg: ToastInput, type?: ToastType) => void;
  dismissToast: (id: string) => void;
  clearAll: () => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setToasts([]);
  }, []);

  const showToast = useCallback(
    (problemOrMsg: ToastInput, type: ToastType = "error") => {
      const id = crypto.randomUUID();

      let item: ToastItem;
      if (typeof problemOrMsg === "string") {
        item = {
          id,
          type,
          title: type.toUpperCase(),
          detail: problemOrMsg,
          durationMs: 4000,
        };
      } else {
        const status = problemOrMsg.status || 400;
        const isServerFatal = status >= 500;
        item = {
          id,
          type: "error",
          title: problemOrMsg.title || `Error (${status})`,
          detail: problemOrMsg.detail || "An error occurred.",
          invalidParams: problemOrMsg.invalid_params,
          retryAfterSeconds: problemOrMsg.retryAfterSeconds,
          // Server errors (500+) are sticky; client errors auto-dismiss unless rate-limited
          durationMs:
            isServerFatal || problemOrMsg.retryAfterSeconds ? undefined : 6000,
        };
      }

      setToasts((prev) => [...prev, item]);
    },
    [],
  );

  return (
    <ToastContext.Provider
      value={{ toasts, showToast, dismissToast, clearAll }}
    >
      {children}
    </ToastContext.Provider>
  );
};

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
