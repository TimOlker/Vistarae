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

/**
 * PrintExportView component (T030, REQ-PLAN-016).
 * Renders a clean, vector-ready multi-page printable layout for itineraries,
 * suppressing UI chrome, expanding days and notes, and triggering window.print().
 */

import React from "react";
import {
  Printer,
  Calendar,
  MapPin,
  Clock,
  DollarSign,
  ArrowLeft,
  Navigation,
  Umbrella,
} from "lucide-react";
import type { ItineraryResponse } from "../../services/itineraryService";

export interface PrintExportViewProps {
  itinerary: ItineraryResponse;
  onClose?: () => void;
}

export const PrintExportView: React.FC<PrintExportViewProps> = ({
  itinerary,
  onClose,
}) => {
  const handlePrint = () => {
    window.print();
  };

  const formatCost = (cents: number | null | undefined): string => {
    if (!cents || cents <= 0) return "Free";
    return `$${(cents / 100).toFixed(2)}`;
  };

  const formatDuration = (hours: number): string => {
    const totalMinutes = Math.round(hours * 60);
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    if (h === 0) return `${m}m`;
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
  };

  const days = itinerary.days ?? [];

  return (
    <div
      className="itinerary-print-page"
      style={{
        maxWidth: "960px",
        margin: "0 auto",
        padding: "32px 24px",
        background: "#ffffff",
        color: "#0f172a",
        minHeight: "100vh",
      }}
    >
      {/* Printable Action Controls (Hidden in @media print) */}
      <div
        className="no-print"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "28px",
          paddingBottom: "16px",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            data-testid="print-back-btn"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 14px",
              borderRadius: "8px",
              background: "#f1f5f9",
              color: "#334155",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <ArrowLeft size={16} />
            <span>Back to Workbench</span>
          </button>
        ) : (
          <div />
        )}

        <button
          type="button"
          onClick={handlePrint}
          data-testid="print-export-btn"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 20px",
            borderRadius: "8px",
            background: "#2563eb",
            color: "#ffffff",
            fontSize: "14px",
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: "0 2px 8px rgba(37,99,235,0.25)",
          }}
        >
          <Printer size={18} />
          <span>Print / Save PDF</span>
        </button>
      </div>

      {/* Header Document Banner */}
      <div
        style={{
          paddingBottom: "24px",
          marginBottom: "32px",
          borderBottom: "2px solid #0f172a",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
          <span style={{ fontSize: "20px" }}>🧭</span>
          <span style={{ fontSize: "14px", fontWeight: 800, letterSpacing: "0.05em", textTransform: "uppercase", color: "#64748b" }}>
            Vistarae Travel Itinerary
          </span>
        </div>

        <h1
          data-testid="print-title"
          style={{
            fontSize: "30px",
            fontWeight: 800,
            letterSpacing: "-0.03em",
            color: "#0f172a",
            marginBottom: "8px",
          }}
        >
          {itinerary.title}
        </h1>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "16px",
            fontSize: "13px",
            color: "#475569",
            marginTop: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <MapPin size={15} color="#2563eb" />
            <span style={{ fontWeight: 600 }}>{itinerary.destination}</span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Calendar size={15} color="#2563eb" />
            <span>
              {itinerary.start_date} &ndash; {itinerary.end_date} ({days.length} {days.length === 1 ? "day" : "days"})
            </span>
          </div>

          {itinerary.budget_cents ? (
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <DollarSign size={15} color="#2563eb" />
              <span>
                Budget: {formatCost(itinerary.budget_cents)} | Est: {formatCost(itinerary.total_estimated_cost_cents)}
              </span>
            </div>
          ) : null}
        </div>
      </div>

      {/* Daily Breakdown */}
      <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
        {days.map((day) => {
          const items = (day.items ?? []).sort((a, b) => a.order_index - b.order_index);
          const durationHours = items.reduce(
            (sum, item) => sum + (parseFloat(item.duration_hours || "0") || 0),
            0
          );

          return (
            <div
              key={day.id}
              className="itinerary-print-day"
              data-testid={`print-day-${day.day_number}`}
              style={{
                borderRadius: "8px",
                border: "1px solid #cbd5e1",
                padding: "20px",
                background: "#fafafa",
              }}
            >
              {/* Day Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  paddingBottom: "12px",
                  marginBottom: "16px",
                  borderBottom: "1px solid #e2e8f0",
                }}
              >
                <div>
                  <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a" }}>
                    Day {day.day_number}
                    {day.calendar_date ? (
                      <span style={{ fontSize: "14px", fontWeight: 500, color: "#64748b", marginLeft: "8px" }}>
                        ({day.calendar_date})
                      </span>
                    ) : null}
                  </h2>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "12px", fontSize: "12px", color: "#475569" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                    <Clock size={14} color="#64748b" />
                    <span>{formatDuration(durationHours)} exploration</span>
                  </div>
                  <div>
                    <span>{formatCost(day.total_cost_cents)}</span>
                  </div>
                </div>
              </div>

              {/* Items List */}
              {items.length === 0 ? (
                <div style={{ fontSize: "13px", color: "#94a3b8", fontStyle: "italic", padding: "8px 0" }}>
                  No activities scheduled for this day.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {items.map((item, idx) => (
                    <div
                      key={item.id}
                      style={{
                        padding: "12px",
                        borderRadius: "6px",
                        background: "#ffffff",
                        border: "1px solid #e2e8f0",
                      }}
                    >
                      {/* Transit Indicator Pill */}
                      {idx > 0 && item.travel_time_prev_minutes ? (
                        <div
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            fontSize: "11px",
                            color: "#2563eb",
                            background: "#eff6ff",
                            padding: "2px 8px",
                            borderRadius: "4px",
                            marginBottom: "8px",
                            fontWeight: 600,
                          }}
                        >
                          <Navigation size={12} />
                          <span>
                            {item.travel_time_prev_minutes} min transit
                            {item.travel_distance_prev_meters
                              ? ` (${(item.travel_distance_prev_meters / 1000).toFixed(1)} km)`
                              : ""}
                          </span>
                        </div>
                      ) : null}

                      <div
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          justifyContent: "space-between",
                          gap: "12px",
                        }}
                      >
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                width: "20px",
                                height: "20px",
                                borderRadius: "50%",
                                background: "#0f172a",
                                color: "#ffffff",
                                fontSize: "11px",
                                fontWeight: 700,
                              }}
                            >
                              {idx + 1}
                            </span>
                            <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#0f172a" }}>
                              {item.title}
                            </h3>
                          </div>

                          {item.notes ? (
                            <p style={{ fontSize: "12px", color: "#475569", marginTop: "4px", marginLeft: "28px" }}>
                              {item.notes}
                            </p>
                          ) : null}

                          {item.is_backup_for_id ? (
                            <div
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "4px",
                                fontSize: "11px",
                                color: "#0891b2",
                                marginTop: "6px",
                                marginLeft: "28px",
                              }}
                            >
                              <Umbrella size={12} />
                              <span>Indoor weather alternative</span>
                            </div>
                          ) : null}
                        </div>

                        <div style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                          {item.start_time && item.end_time ? (
                            <div style={{ fontSize: "12px", fontWeight: 600, color: "#0f172a" }}>
                              {item.start_time.slice(0, 5)} &ndash; {item.end_time.slice(0, 5)}
                            </div>
                          ) : null}
                          <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                            {formatCost(item.cost_cents)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer Branding */}
      <div
        style={{
          marginTop: "48px",
          paddingTop: "16px",
          borderTop: "1px solid #e2e8f0",
          textAlign: "center",
          fontSize: "12px",
          color: "#94a3b8",
        }}
      >
        Generated with Vistarae &bull; AI Travel &amp; POI Engine
      </div>
    </div>
  );
};
