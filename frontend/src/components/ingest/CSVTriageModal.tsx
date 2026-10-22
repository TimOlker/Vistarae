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

import React, { useEffect, useState } from "react";
import { Modal } from "../common/Modal";
import {
  triageStorage,
  type TriageDecision,
} from "../../services/triageStorage";
import { apiFetch } from "../../services/api";
import { useToast } from "../../context/ToastContext";
import { Layers, Check, X, ArrowRight, ShieldCheck } from "lucide-react";

export interface DuplicatePair {
  row_number: number;
  match_type: "POTENTIAL_DUPLICATE" | "NEARBY_PARENT";
  similarity_score: number;
  distance_meters: number;
  staged_poi: {
    name: string;
    latitude: number;
    longitude: number;
    city?: string;
    tags?: string[];
  };
  existing_poi: {
    id: string;
    name: string;
    latitude: number;
    longitude: number;
    city?: string;
    visit_state?: string;
  };
}

interface CSVTriageModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onTriageComplete: () => void;
}

export const CSVTriageModal: React.FC<CSVTriageModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onTriageComplete,
}) => {
  const { showToast } = useToast();

  const [duplicates, setDuplicates] = useState<DuplicatePair[]>([]);
  const [decisions, setDecisions] = useState<Record<number, TriageDecision>>(
    {},
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load candidates and restore persisted decisions from IndexedDB
  useEffect(() => {
    if (!isOpen || !jobId) return;

    const loadData = async () => {
      setIsLoading(true);
      try {
        // Fetch duplicate candidate pairs from backend
        const res = await apiFetch<{ items: DuplicatePair[] }>(
          `/api/ingest/jobs/${jobId}/duplicates`,
        );
        const pairs = res.items || [];
        setDuplicates(pairs);

        // Restore staged decisions from IndexedDB (survives refreshes)
        const saved = await triageStorage.getJobRecord(jobId);
        if (saved && saved.decisions) {
          setDecisions(saved.decisions);
        } else {
          // Default all to COMMITTED (create new)
          const initial: Record<number, TriageDecision> = {};
          pairs.forEach((p) => {
            initial[p.row_number] = "COMMITTED";
          });
          setDecisions(initial);
        }
      } catch (err) {
        console.error("Failed to load duplicate candidates:", err);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [isOpen, jobId]);

  const handleDecisionToggle = async (
    rowNumber: number,
    decision: TriageDecision,
  ) => {
    setDecisions((prev) => ({ ...prev, [rowNumber]: decision }));

    // Persist in IndexedDB immediately
    if (jobId) {
      await triageStorage.saveDecision(jobId, rowNumber, decision);
    }
  };

  const handleCommitTriage = async () => {
    if (!jobId) return;

    setIsSubmitting(true);
    try {
      const items = Object.entries(decisions).map(([row, decision]) => ({
        row_number: parseInt(row, 10),
        decision,
      }));

      await apiFetch(`/api/ingest/jobs/${jobId}/triage`, {
        method: "POST",
        body: JSON.stringify({ decisions: items }),
      });

      // Clear local IndexedDB record upon successful submission
      await triageStorage.deleteJobRecord(jobId);

      showToast("Duplicate triage submitted successfully!", "success");
      onTriageComplete();
      onClose();
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(
        errorObj.problem ||
          errorObj.message ||
          "Failed to submit triage decisions",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen || !jobId) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Review Duplicate Candidates"
      maxWidth="720px"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "13px",
            color: "var(--text-secondary)",
          }}
        >
          <Layers size={18} color="var(--accent, #2563eb)" />
          <span>
            {duplicates.length} records matched existing locations within
            spatial radius. Selections are auto-saved in browser storage.
          </span>
        </div>

        {isLoading ? (
          <div
            style={{
              padding: "32px",
              textAlign: "center",
              color: "var(--text-muted)",
            }}
          >
            Loading duplicate candidates...
          </div>
        ) : duplicates.length === 0 ? (
          <div
            style={{
              padding: "24px",
              textAlign: "center",
              color: "var(--text-muted)",
            }}
          >
            No duplicates require review for this job.
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              maxHeight: "55vh",
              overflowY: "auto",
            }}
          >
            {duplicates.map((pair) => {
              const currentDecision = decisions[pair.row_number] || "COMMITTED";

              return (
                <div
                  key={pair.row_number}
                  style={{
                    border: "1px solid var(--border-color, #e2e8f0)",
                    borderRadius: "var(--radius-md, 8px)",
                    padding: "14px",
                    background: "var(--bg-surface, #ffffff)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                  }}
                >
                  {/* Match metrics badge */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      fontSize: "11px",
                    }}
                  >
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: "4px",
                        background:
                          pair.match_type === "POTENTIAL_DUPLICATE"
                            ? "#fef2f2"
                            : "#eff6ff",
                        color:
                          pair.match_type === "POTENTIAL_DUPLICATE"
                            ? "#b91c1c"
                            : "#1d4ed8",
                        fontWeight: 700,
                      }}
                    >
                      {pair.match_type.replace(/_/g, " ")}
                    </span>
                    <span style={{ color: "var(--text-muted)" }}>
                      Similarity: {(pair.similarity_score * 100).toFixed(0)}% •
                      Distance: {pair.distance_meters.toFixed(0)}m
                    </span>
                  </div>

                  {/* Side-by-side comparison */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: "12px",
                      fontSize: "12px",
                    }}
                  >
                    {/* Staged POI */}
                    <div
                      style={{
                        padding: "10px",
                        background: "var(--bg-hover, #f8fafc)",
                        borderRadius: "6px",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "10px",
                          textTransform: "uppercase",
                          color: "var(--text-muted)",
                          fontWeight: 700,
                        }}
                      >
                        From CSV (Row {pair.row_number})
                      </span>
                      <p
                        style={{
                          fontWeight: 700,
                          fontSize: "14px",
                          marginTop: "2px",
                        }}
                      >
                        {pair.staged_poi.name}
                      </p>
                      <p style={{ color: "var(--text-secondary)" }}>
                        {pair.staged_poi.city ||
                          `${pair.staged_poi.latitude.toFixed(
                            4,
                          )}, ${pair.staged_poi.longitude.toFixed(4)}`}
                      </p>
                    </div>

                    {/* Existing POI */}
                    <div
                      style={{
                        padding: "10px",
                        background: "var(--bg-hover, #f8fafc)",
                        borderRadius: "6px",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "10px",
                          textTransform: "uppercase",
                          color: "var(--text-muted)",
                          fontWeight: 700,
                        }}
                      >
                        Existing in Database
                      </span>
                      <p
                        style={{
                          fontWeight: 700,
                          fontSize: "14px",
                          marginTop: "2px",
                        }}
                      >
                        {pair.existing_poi.name}
                      </p>
                      <p style={{ color: "var(--text-secondary)" }}>
                        {pair.existing_poi.city ||
                          `${pair.existing_poi.latitude.toFixed(
                            4,
                          )}, ${pair.existing_poi.longitude.toFixed(4)}`}
                      </p>
                    </div>
                  </div>

                  {/* Decision toggles */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "flex-end",
                      gap: "8px",
                      paddingTop: "4px",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        handleDecisionToggle(pair.row_number, "COMMITTED")
                      }
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        padding: "6px 12px",
                        borderRadius: "6px",
                        background:
                          currentDecision === "COMMITTED"
                            ? "var(--accent, #2563eb)"
                            : "var(--bg-hover)",
                        color:
                          currentDecision === "COMMITTED"
                            ? "#ffffff"
                            : "var(--text-secondary)",
                        fontSize: "12px",
                        fontWeight: 600,
                      }}
                    >
                      <Check size={14} />
                      <span>Create New POI</span>
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        handleDecisionToggle(pair.row_number, "REJECTED")
                      }
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        padding: "6px 12px",
                        borderRadius: "6px",
                        background:
                          currentDecision === "REJECTED"
                            ? "var(--danger, #ef4444)"
                            : "var(--bg-hover)",
                        color:
                          currentDecision === "REJECTED"
                            ? "#ffffff"
                            : "var(--text-secondary)",
                        fontSize: "12px",
                        fontWeight: 600,
                      }}
                    >
                      <X size={14} />
                      <span>Skip / Ignore</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Commit footer */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: "12px",
            borderTop: "1px solid var(--border-color, #e2e8f0)",
            paddingTop: "12px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "11px",
              color: "var(--text-muted)",
            }}
          >
            <ShieldCheck size={14} />
            <span>Persisted locally in IndexedDB (7-day TTL)</span>
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--bg-hover, #f1f5f9)",
                color: "var(--text-secondary)",
                fontWeight: 600,
                fontSize: "13px",
              }}
            >
              Close
            </button>
            <button
              type="button"
              disabled={isSubmitting || duplicates.length === 0}
              onClick={handleCommitTriage}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 20px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--accent, #2563eb)",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "13px",
                cursor:
                  isSubmitting || duplicates.length === 0
                    ? "not-allowed"
                    : "pointer",
                opacity: isSubmitting || duplicates.length === 0 ? 0.6 : 1,
              }}
            >
              <span>
                {isSubmitting ? "Committing..." : "Commit All Decisions"}
              </span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
