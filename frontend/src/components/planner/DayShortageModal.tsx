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

import React from "react";
import { AlertTriangle, CalendarPlus, XCircle, X } from "lucide-react";
import type { CircuitBreakerWarning } from "../../services/itineraryService";

interface DayShortageModalProps {
  warning: CircuitBreakerWarning;
  isOpen: boolean;
  onClose: () => void;
  onExtendTrip?: () => void;
}

export const DayShortageModal: React.FC<DayShortageModalProps> = ({
  warning,
  isOpen,
  onClose,
  onExtendTrip,
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(4px)",
        padding: "16px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "480px",
          backgroundColor: "var(--bg-card)",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-color)",
          boxShadow: "var(--shadow-lg)",
          padding: "24px",
          animation: "slideUp var(--transition-normal) forwards",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "36px",
                height: "36px",
                borderRadius: "var(--radius-full)",
                backgroundColor: "rgba(245, 158, 11, 0.12)",
                color: "var(--warning)",
              }}
            >
              <AlertTriangle size={20} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>
              Insufficient Days for Multi-Day Attraction
            </h3>
          </div>

          <button
            type="button"
            onClick={onClose}
            style={{ color: "var(--text-muted)" }}
            aria-label="Close dialog"
          >
            <X size={20} />
          </button>
        </div>

        <p
          style={{
            fontSize: "0.9rem",
            color: "var(--text-secondary)",
            lineHeight: 1.5,
            marginBottom: "20px",
          }}
        >
          {warning.message}
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {onExtendTrip ? (
            <button
              type="button"
              onClick={() => {
                onExtendTrip();
                onClose();
              }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                padding: "10px 16px",
                borderRadius: "var(--radius-md)",
                backgroundColor: "var(--accent)",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "0.9rem",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <CalendarPlus size={16} /> Extend Trip Duration
            </button>
          ) : null}

          <button
            type="button"
            onClick={onClose}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              backgroundColor: "var(--bg-hover)",
              border: "1px solid var(--border-color)",
              color: "var(--text-primary)",
              fontWeight: 500,
              fontSize: "0.9rem",
            }}
          >
            <XCircle size={16} /> Adjust Scheduled Activities
          </button>
        </div>
      </div>
    </div>
  );
};
