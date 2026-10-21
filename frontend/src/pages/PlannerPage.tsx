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
 * PlannerPage component (T016, REQ-PLAN-001, REQ-PLAN-002, REQ-PLAN-005).
 * Lists all user itineraries and provides an AI trip generation modal with
 * destination, 30-day date range validation, budget, and travel style prompt.
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  Calendar,
  MapPin,
  DollarSign,
  Plus,
  Trash2,
  ArrowRight,
  Compass,
  AlertCircle,
  Loader2,
} from "lucide-react";
import {
  itineraryService,
  type ItinerarySummary,
  type ItineraryGenerateRequest,
} from "../services/itineraryService";
import { useToast } from "../context/ToastContext";

interface PlannerPageProps {
  onNavigateToTrip: (itineraryId: string) => void;
}

export const PlannerPage: React.FC<PlannerPageProps> = ({ onNavigateToTrip }) => {
  const { showToast } = useToast();
  const [itineraries, setItineraries] = useState<ItinerarySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Form State
  const [destination, setDestination] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [budgetDollars, setBudgetDollars] = useState("");
  const [prompt, setPrompt] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const fetchItineraries = useCallback(async () => {
    try {
      setLoading(true);
      const data = await itineraryService.listItineraries();
      setItineraries(data);
    } catch (err) {
      console.error("Failed to load itineraries:", err);
      showToast("Unable to load itineraries. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchItineraries();
  }, [fetchItineraries]);

  const handleOpenModal = () => {
    setDestination("");
    setStartDate("");
    setEndDate("");
    setBudgetDollars("");
    setPrompt("");
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!destination.trim()) {
      setFormError("Destination is required.");
      return;
    }
    if (!startDate || !endDate) {
      setFormError("Start and end dates are required.");
      return;
    }

    const start = new Date(startDate);
    const end = new Date(endDate);

    if (end < start) {
      setFormError("End date must be after or equal to start date.");
      return;
    }

    const diffDays = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1;
    if (diffDays > 30) {
      setFormError(`Trip duration cannot exceed 30 days (selected ${diffDays} days).`);
      return;
    }

    const budgetCents = budgetDollars.trim()
      ? Math.round(parseFloat(budgetDollars) * 100)
      : undefined;

    const payload: ItineraryGenerateRequest = {
      destination: destination.trim(),
      start_date: startDate,
      end_date: endDate,
      budget_cents: budgetCents,
      prompt: prompt.trim() || `Explore top highlights and sights in ${destination.trim()}`,
      currency: "USD",
    };

    try {
      setGenerating(true);
      const created = await itineraryService.generateItinerary(payload);
      showToast("Trip itinerary generated successfully!", "success");
      setIsModalOpen(false);
      onNavigateToTrip(created.id);
    } catch (err: unknown) {
      console.error("Failed to generate itinerary:", err);
      const errorMsg =
        err instanceof Error ? err.message : "Failed to synthesize itinerary.";
      setFormError(errorMsg);
      showToast(errorMsg, "error");
    } finally {
      setGenerating(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this itinerary?")) return;

    try {
      await itineraryService.deleteItinerary(id);
      setItineraries((prev) => prev.filter((it) => it.id !== id));
      showToast("Itinerary deleted.", "info");
    } catch (err) {
      console.error("Failed to delete itinerary:", err);
      showToast("Failed to delete itinerary.", "error");
    }
  };

  const formatCost = (cents: number | null | undefined): string => {
    if (!cents || cents <= 0) return "Free";
    return `$${(cents / 100).toFixed(2)}`;
  };

  return (
    <div
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "32px 24px",
      }}
    >
      {/* Header Banner */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "32px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <Compass size={24} color="var(--accent, #2563eb)" />
            <h1 style={{ fontSize: "28px", fontWeight: 800, letterSpacing: "-0.02em" }}>
              AI Trip Planner
            </h1>
          </div>
          <p style={{ color: "var(--text-secondary, #475569)", fontSize: "14px" }}>
            Synthesize your saved POIs into executable day-by-day itineraries with smart routes and budgeting.
          </p>
        </div>

        <button
          type="button"
          data-testid="create-trip-btn"
          onClick={handleOpenModal}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 20px",
            borderRadius: "var(--radius-md, 8px)",
            background: "var(--accent, #2563eb)",
            color: "#ffffff",
            fontSize: "14px",
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: "0 2px 8px rgba(37,99,235,0.25)",
          }}
        >
          <Sparkles size={16} />
          <span>New AI Itinerary</span>
        </button>
      </div>

      {/* Itineraries List */}
      {loading ? (
        <div
          data-testid="itineraries-loading"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "64px 0",
            color: "var(--text-muted, #94a3b8)",
            gap: "10px",
          }}
        >
          <Loader2 size={24} className="animate-spin" />
          <span>Loading your travel itineraries...</span>
        </div>
      ) : itineraries.length === 0 ? (
        <div
          data-testid="itineraries-empty"
          style={{
            textAlign: "center",
            padding: "64px 24px",
            background: "var(--bg-surface, #ffffff)",
            borderRadius: "var(--radius-lg, 12px)",
            border: "1px dashed var(--border-color, #e2e8f0)",
          }}
        >
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "50%",
              background: "var(--accent-light, #eff6ff)",
              color: "var(--accent, #2563eb)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
            }}
          >
            <Sparkles size={28} />
          </div>
          <h2 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "8px" }}>
            No itineraries planned yet
          </h2>
          <p style={{ color: "var(--text-secondary, #475569)", fontSize: "14px", maxWidth: "420px", margin: "0 auto 20px" }}>
            Prompt Gemini to craft an optimized schedule from your saved places, or explore a new destination corridor.
          </p>
          <button
            type="button"
            onClick={handleOpenModal}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "10px 18px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontSize: "14px",
              fontWeight: 600,
            }}
          >
            <Plus size={16} />
            <span>Create First Trip</span>
          </button>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: "20px",
          }}
        >
          {itineraries.map((it) => (
            <div
              key={it.id}
              data-testid={`itinerary-card-${it.id}`}
              onClick={() => onNavigateToTrip(it.id)}
              style={{
                background: "var(--bg-surface, #ffffff)",
                border: "1px solid var(--border-color, #e2e8f0)",
                borderRadius: "var(--radius-md, 10px)",
                padding: "20px",
                cursor: "pointer",
                transition: "all var(--transition-fast, 150ms)",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: "16px",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "var(--shadow-md, 0 4px 6px -1px rgba(0,0,0,0.1))";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "none";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "10px" }}>
                  <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary, #0f172a)" }}>
                    {it.title}
                  </h3>
                  <button
                    type="button"
                    title="Delete Itinerary"
                    data-testid={`delete-itinerary-${it.id}`}
                    onClick={(e) => handleDelete(it.id, e)}
                    style={{
                      padding: "4px",
                      borderRadius: "4px",
                      color: "var(--text-muted, #94a3b8)",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "var(--danger, #ef4444)")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted, #94a3b8)")}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "12px", fontSize: "13px", color: "var(--text-secondary, #475569)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <MapPin size={14} color="var(--accent, #2563eb)" />
                    <span>{it.destination}</span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <Calendar size={14} color="var(--accent, #2563eb)" />
                    <span>
                      {it.start_date} &ndash; {it.end_date}
                    </span>
                  </div>

                  {it.budget_cents ? (
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <DollarSign size={14} color="var(--accent, #2563eb)" />
                      <span>
                        Budget: {formatCost(it.budget_cents)} | Est: {formatCost(it.total_estimated_cost_cents)}
                      </span>
                    </div>
                  ) : null}
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  paddingTop: "12px",
                  borderTop: "1px solid var(--border-color, #e2e8f0)",
                  fontSize: "12px",
                  color: "var(--accent, #2563eb)",
                  fontWeight: 600,
                }}
              >
                <span>Open Workbench</span>
                <ArrowRight size={14} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Trip Generation Modal */}
      {isModalOpen && (
        <div
          data-testid="trip-generation-modal"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.6)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              borderRadius: "var(--radius-lg, 12px)",
              width: "100%",
              maxWidth: "520px",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.2)",
              border: "1px solid var(--border-color, #e2e8f0)",
              overflow: "hidden",
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "16px 20px",
                borderBottom: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-primary, #f8fafc)",
              }}
            >
              <Sparkles size={18} color="var(--accent, #2563eb)" />
              <h2 style={{ fontSize: "16px", fontWeight: 700 }}>Synthesize Trip with Gemini AI</h2>
            </div>

            {/* Modal Body Form */}
            <form onSubmit={handleGenerate} style={{ padding: "20px" }}>
              {formError && (
                <div
                  data-testid="trip-form-error"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    background: "#fef2f2",
                    border: "1px solid #fecaca",
                    color: "#b91c1c",
                    fontSize: "13px",
                    marginBottom: "16px",
                  }}
                >
                  <AlertCircle size={16} />
                  <span>{formError}</span>
                </div>
              )}

              <div style={{ marginBottom: "14px" }}>
                <label
                  htmlFor="dest-input"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #475569)", marginBottom: "4px" }}
                >
                  Destination Corridor *
                </label>
                <input
                  id="dest-input"
                  type="text"
                  required
                  placeholder="e.g. Olympic National Park & Seattle"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "6px",
                    border: "1px solid var(--border-color, #cbd5e1)",
                    fontSize: "14px",
                    background: "var(--bg-card, #ffffff)",
                    color: "var(--text-primary, #0f172a)",
                  }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "14px" }}>
                <div>
                  <label
                    htmlFor="start-date-input"
                    style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #475569)", marginBottom: "4px" }}
                  >
                    Start Date *
                  </label>
                  <input
                    id="start-date-input"
                    type="date"
                    required
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      border: "1px solid var(--border-color, #cbd5e1)",
                      fontSize: "13px",
                      background: "var(--bg-card, #ffffff)",
                      color: "var(--text-primary, #0f172a)",
                    }}
                  />
                </div>

                <div>
                  <label
                    htmlFor="end-date-input"
                    style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #475569)", marginBottom: "4px" }}
                  >
                    End Date (max 30 days) *
                  </label>
                  <input
                    id="end-date-input"
                    type="date"
                    required
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: "6px",
                      border: "1px solid var(--border-color, #cbd5e1)",
                      fontSize: "13px",
                      background: "var(--bg-card, #ffffff)",
                      color: "var(--text-primary, #0f172a)",
                    }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: "14px" }}>
                <label
                  htmlFor="budget-input"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #475569)", marginBottom: "4px" }}
                >
                  Budget ($ USD, optional)
                </label>
                <input
                  id="budget-input"
                  type="number"
                  min="0"
                  step="10"
                  placeholder="e.g. 1200"
                  value={budgetDollars}
                  onChange={(e) => setBudgetDollars(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "6px",
                    border: "1px solid var(--border-color, #cbd5e1)",
                    fontSize: "14px",
                    background: "var(--bg-card, #ffffff)",
                    color: "var(--text-primary, #0f172a)",
                  }}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label
                  htmlFor="prompt-input"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #475569)", marginBottom: "4px" }}
                >
                  Travel Style &amp; Preferences
                </label>
                <textarea
                  id="prompt-input"
                  rows={3}
                  placeholder="e.g. Coastal hikes, fresh seafood, relaxed afternoons with local coffee..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: "6px",
                    border: "1px solid var(--border-color, #cbd5e1)",
                    fontSize: "13px",
                    background: "var(--bg-card, #ffffff)",
                    color: "var(--text-primary, #0f172a)",
                    resize: "vertical",
                  }}
                />
              </div>

              {/* Modal Footer */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "flex-end",
                  gap: "10px",
                }}
              >
                <button
                  type="button"
                  disabled={generating}
                  onClick={() => setIsModalOpen(false)}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "6px",
                    border: "1px solid var(--border-color, #cbd5e1)",
                    background: "transparent",
                    color: "var(--text-secondary, #475569)",
                    fontSize: "13px",
                    fontWeight: 600,
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={generating}
                  data-testid="submit-generate-trip"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "8px 18px",
                    borderRadius: "6px",
                    background: "var(--accent, #2563eb)",
                    color: "#ffffff",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: generating ? "not-allowed" : "pointer",
                    opacity: generating ? 0.7 : 1,
                  }}
                >
                  {generating ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      <span>Synthesizing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={15} />
                      <span>Synthesize Schedule</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
