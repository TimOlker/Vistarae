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

import React, { useEffect, useState } from "react";
import { Modal } from "../common/Modal";
import {
  ingestApi,
  type BulkEnrichmentSummaryResult,
  type CandidateIssueDetail,
} from "../../services/ingestApi";
import {
  CheckCircle2,
  AlertOctagon,
  StopCircle,
  XCircle,
  Clock,
  Cpu,
  Layers,
  ArrowRight,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";

export interface CSVEnrichmentSummaryModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onFilterIncomplete?: () => void;
}

export const CSVEnrichmentSummaryModal: React.FC<
  CSVEnrichmentSummaryModalProps
> = ({ jobId, isOpen, onClose, onFilterIncomplete }) => {
  const [summary, setSummary] = useState<BulkEnrichmentSummaryResult | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    "all" | "RESOURCE_EXHAUSTION" | "INPUT_DATA_ISSUE" | "TEMPORARY_FAILURE" | "INTERRUPTED"
  >("all");

  useEffect(() => {
    if (!isOpen || !jobId) {
      setSummary(null);
      setError(null);
      setActiveTab("all");
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    ingestApi
      .getBulkEnrichmentSummary(jobId)
      .then((data) => {
        if (isMounted) {
          setSummary(data);
          setLoading(false);
        }
      })
      .catch((err: any) => {
        if (isMounted) {
          setError(err?.message || "Failed to load session summary");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, jobId]);

  const getStatusBadge = (
    status?: string,
    unprocessedCount: number = 0,
    termReason: string = "",
  ) => {
    switch (status) {
      case "COMPLETED":
        if (unprocessedCount > 0) {
          return {
            icon: <AlertOctagon size={24} color="#d97706" />,
            title: "Enrichment Run Partially Completed",
            bg: "#fffbeb",
            border: "#fde68a",
            text: "#92400e",
          };
        }
        return {
          icon: <CheckCircle2 size={24} color="#16a34a" />,
          title: "Enrichment Run Completed Successfully",
          bg: "#f0fdf4",
          border: "#bbf7d0",
          text: "#166534",
        };
      case "BLOCKED":
        return {
          icon: <AlertOctagon size={24} color="#d97706" />,
          title: "Run Halted by Circuit Breaker (Quota / Limits)",
          bg: "#fffbeb",
          border: "#fde68a",
          text: "#92400e",
        };
      case "CANCELLED": {
        const isHeartbeatTimeout =
          termReason.toLowerCase().includes("heartbeat") ||
          termReason.toLowerCase().includes("disconnected");
        if (isHeartbeatTimeout) {
          return {
            icon: <AlertTriangle size={24} color="#d97706" />,
            title: "Enrichment Interrupted (Background Tab / Disconnected)",
            bg: "#fffbeb",
            border: "#fde68a",
            text: "#92400e",
          };
        }
        return {
          icon: <StopCircle size={24} color="#64748b" />,
          title: "Enrichment Cancelled by User",
          bg: "#f8fafc",
          border: "#cbd5e1",
          text: "#334155",
        };
      }
      case "FAILED":
      default:
        return {
          icon: <XCircle size={24} color="#dc2626" />,
          title: "Enrichment Halted Due to Errors",
          bg: "#fef2f2",
          border: "#fecaca",
          text: "#991b1b",
        };
    }
  };

  const getCategoryPill = (category: string) => {
    switch (category) {
      case "RESOURCE_EXHAUSTION":
        return {
          label: "Resource Exhaustion",
          bg: "#fef2f2",
          border: "#fecaca",
          textColor: "#991b1b",
          pillBg: "#fee2e2",
        };
      case "INPUT_DATA_ISSUE":
        return {
          label: "Input Data Issue",
          bg: "#fffbeb",
          border: "#fde68a",
          textColor: "#92400e",
          pillBg: "#fef3c7",
        };
      case "TEMPORARY_FAILURE":
        return {
          label: "Temporary Failure",
          bg: "#fff7ed",
          border: "#fed7aa",
          textColor: "#c2410c",
          pillBg: "#ffedd5",
        };
      case "INTERRUPTED":
      default:
        return {
          label: "Interrupted / Unprocessed",
          bg: "#f8fafc",
          border: "#cbd5e1",
          textColor: "#334155",
          pillBg: "#e2e8f0",
        };
    }
  };

  const badge = getStatusBadge(
    summary?.status,
    summary?.unprocessed_count ?? 0,
    summary?.termination_reason ?? "",
  );

  const issuesList: CandidateIssueDetail[] = summary?.candidate_issues ?? [];
  const resourceCount = issuesList.filter(
    (i) => i.category === "RESOURCE_EXHAUSTION",
  ).length;
  const inputDataCount = issuesList.filter(
    (i) => i.category === "INPUT_DATA_ISSUE",
  ).length;
  const tempFailCount = issuesList.filter(
    (i) => i.category === "TEMPORARY_FAILURE",
  ).length;
  const interruptedCount = issuesList.filter(
    (i) => i.category === "INTERRUPTED",
  ).length;

  const totalIssuesCount =
    issuesList.length > 0
      ? issuesList.length
      : (summary?.temporary_error_count ?? 0) +
        (summary?.blocking_error_count ?? 0) +
        (summary?.internal_error_count ?? 0) +
        (summary?.unprocessed_count ?? 0);

  const filteredIssues =
    activeTab === "all"
      ? issuesList
      : issuesList.filter((i) => i.category === activeTab);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Bulk AI Enrichment Run Summary"
      maxWidth="720px"
    >
      <div
        data-testid="enrichment-summary-modal"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          padding: "6px 2px",
          color: "#1e293b",
        }}
      >
        {loading ? (
          <div
            style={{ textAlign: "center", padding: "30px", color: "#64748b" }}
          >
            Loading session statistics...
          </div>
        ) : error ? (
          <div
            style={{
              padding: "16px",
              backgroundColor: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: "8px",
              color: "#991b1b",
              fontSize: "13px",
            }}
          >
            {error}
          </div>
        ) : summary ? (
          <>
            {/* Status Header Banner (REQ-ENR-026) */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "14px",
                padding: "14px 16px",
                backgroundColor: badge.bg,
                border: `1px solid ${badge.border}`,
                borderRadius: "10px",
              }}
            >
              <div
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "50%",
                  backgroundColor: "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                }}
              >
                {badge.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: "14px",
                    color: badge.text,
                  }}
                >
                  {badge.title}
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: badge.text,
                    opacity: 0.9,
                    marginTop: "2px",
                  }}
                >
                  {summary.termination_reason || "Session concluded."}
                </div>
              </div>
            </div>

            {/* Metrics Breakdown Grid (REQ-ENR-026, REQ-ENR-027) */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr",
                gap: "10px",
              }}
            >
              <div
                style={{
                  padding: "12px",
                  backgroundColor: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                }}
              >
                <div
                  style={{
                    fontSize: "10px",
                    color: "#64748b",
                    textTransform: "uppercase",
                    fontWeight: 700,
                  }}
                >
                  Total Enqueued
                </div>
                <div
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    color: "#1e293b",
                    marginTop: "2px",
                  }}
                >
                  {summary.total_candidates}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: "#64748b",
                    marginTop: "2px",
                  }}
                >
                  Unprocessed: {summary.unprocessed_count}
                </div>
              </div>

              <div
                style={{
                  padding: "12px",
                  backgroundColor: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  borderRadius: "8px",
                }}
              >
                <div
                  style={{
                    fontSize: "10px",
                    color: "#166534",
                    textTransform: "uppercase",
                    fontWeight: 700,
                  }}
                >
                  Succeeded
                </div>
                <div
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    color: "#15803d",
                    marginTop: "2px",
                  }}
                >
                  {summary.succeeded_count}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: "#166534",
                    marginTop: "2px",
                  }}
                >
                  Success rate:{" "}
                  {summary.total_candidates > 0
                    ? `${Math.round(
                        (summary.succeeded_count / summary.total_candidates) *
                          100,
                      )}%`
                    : "0%"}
                </div>
              </div>

              <div
                style={{
                  padding: "12px",
                  backgroundColor:
                    totalIssuesCount > 0 ? "#fef2f2" : "#f8fafc",
                  border: `1px solid ${
                    totalIssuesCount > 0 ? "#fecaca" : "#e2e8f0"
                  }`,
                  borderRadius: "8px",
                }}
              >
                <div
                  style={{
                    fontSize: "10px",
                    color: totalIssuesCount > 0 ? "#991b1b" : "#64748b",
                    textTransform: "uppercase",
                    fontWeight: 700,
                  }}
                >
                  Issues & Incomplete
                </div>
                <div
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    color: totalIssuesCount > 0 ? "#dc2626" : "#1e293b",
                    marginTop: "2px",
                  }}
                >
                  {totalIssuesCount}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: totalIssuesCount > 0 ? "#b91c1c" : "#64748b",
                    marginTop: "2px",
                  }}
                >
                  Temp: {summary.temporary_error_count} | Blk:{" "}
                  {summary.blocking_error_count} | Unproc:{" "}
                  {summary.unprocessed_count}
                </div>
              </div>
            </div>

            {/* Performance and Resources Consumed (REQ-ENR-028) */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "10px",
              }}
            >
              <div
                style={{
                  padding: "10px 14px",
                  backgroundColor: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Clock size={20} color="#64748b" />
                <div>
                  <div
                    style={{
                      fontSize: "10px",
                      color: "#64748b",
                      textTransform: "uppercase",
                      fontWeight: 700,
                    }}
                  >
                    Total Wall-Clock Time
                  </div>
                  <div
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#1e293b",
                    }}
                  >
                    {(summary.total_duration_ms / 1000).toFixed(1)}s (Avg:{" "}
                    {(summary.average_duration_ms / 1000).toFixed(1)}s/POI)
                  </div>
                </div>
              </div>

              <div
                style={{
                  padding: "10px 14px",
                  backgroundColor: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Cpu size={20} color="#64748b" />
                <div>
                  <div
                    style={{
                      fontSize: "10px",
                      color: "#64748b",
                      textTransform: "uppercase",
                      fontWeight: 700,
                    }}
                  >
                    Resources Consumed
                  </div>
                  <div
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#1e293b",
                    }}
                  >
                    {summary.total_resources_used} API calls / units
                  </div>
                </div>
              </div>
            </div>

            {/* Candidate Diagnostic & Issue Details (Feedback on Why POIs Failed / Incomplete) */}
            {issuesList.length > 0 && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  marginTop: "4px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div
                    style={{
                      fontWeight: 700,
                      fontSize: "13px",
                      color: "#1e293b",
                    }}
                  >
                    POI Diagnostic & Issue Details ({issuesList.length})
                  </div>
                  <div style={{ fontSize: "11px", color: "#64748b" }}>
                    Filter by issue category below
                  </div>
                </div>

                {/* Filter Tabs */}
                <div
                  style={{
                    display: "flex",
                    gap: "6px",
                    overflowX: "auto",
                    paddingBottom: "2px",
                  }}
                >
                  {[
                    { key: "all", label: `All (${issuesList.length})` },
                    ...(resourceCount > 0
                      ? [
                          {
                            key: "RESOURCE_EXHAUSTION",
                            label: `🔴 Resource Limits (${resourceCount})`,
                          },
                        ]
                      : []),
                    ...(inputDataCount > 0
                      ? [
                          {
                            key: "INPUT_DATA_ISSUE",
                            label: `🟡 Input Data (${inputDataCount})`,
                          },
                        ]
                      : []),
                    ...(tempFailCount > 0
                      ? [
                          {
                            key: "TEMPORARY_FAILURE",
                            label: `🟠 Temporary (${tempFailCount})`,
                          },
                        ]
                      : []),
                    ...(interruptedCount > 0
                      ? [
                          {
                            key: "INTERRUPTED",
                            label: `⚪ Interrupted (${interruptedCount})`,
                          },
                        ]
                      : []),
                  ].map((tab) => (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => setActiveTab(tab.key as any)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: "14px",
                        fontSize: "11px",
                        fontWeight: activeTab === tab.key ? 700 : 500,
                        backgroundColor:
                          activeTab === tab.key ? "#2563eb" : "#f1f5f9",
                        color: activeTab === tab.key ? "#ffffff" : "#475569",
                        border: "none",
                        cursor: "pointer",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Scrollable Issues List */}
                <div
                  style={{
                    maxHeight: "220px",
                    overflowY: "auto",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    paddingRight: "4px",
                  }}
                >
                  {filteredIssues.map((issue, idx) => {
                    const pill = getCategoryPill(issue.category);
                    return (
                      <div
                        key={issue.candidate_id || idx}
                        style={{
                          padding: "10px 12px",
                          backgroundColor: pill.bg,
                          border: `1px solid ${pill.border}`,
                          borderRadius: "8px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "4px",
                          fontSize: "12px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            <span
                              style={{
                                fontWeight: 700,
                                color: "#334155",
                                backgroundColor: "#ffffff",
                                padding: "1px 6px",
                                borderRadius: "4px",
                                border: "1px solid #e2e8f0",
                                fontSize: "10px",
                              }}
                            >
                              Row #{issue.row_index || idx + 1}
                            </span>
                            <span
                              style={{ fontWeight: 600, color: "#1e293b" }}
                            >
                              {issue.poi_name}
                            </span>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                            }}
                          >
                            <span
                              style={{
                                fontSize: "10px",
                                fontWeight: 600,
                                color: pill.textColor,
                                backgroundColor: pill.pillBg,
                                padding: "2px 8px",
                                borderRadius: "10px",
                              }}
                            >
                              {pill.label}
                            </span>
                            {issue.is_retryable ? (
                              <span
                                style={{
                                  fontSize: "10px",
                                  fontWeight: 600,
                                  color: "#15803d",
                                  backgroundColor: "#dcfce7",
                                  padding: "2px 6px",
                                  borderRadius: "10px",
                                }}
                              >
                                ✓ Safe to Retry
                              </span>
                            ) : (
                              <span
                                style={{
                                  fontSize: "10px",
                                  fontWeight: 600,
                                  color: "#b45309",
                                  backgroundColor: "#fef3c7",
                                  padding: "2px 6px",
                                  borderRadius: "10px",
                                }}
                              >
                                ⚠️ Action Needed
                              </span>
                            )}
                          </div>
                        </div>

                        <div style={{ color: "#334155", marginTop: "2px" }}>
                          <strong>Reason: </strong>
                          {issue.reason}
                        </div>

                        <div
                          style={{
                            color: "#64748b",
                            fontSize: "11px",
                            fontStyle: "italic",
                            marginTop: "2px",
                          }}
                        >
                          <strong>Suggested Action: </strong>
                          {issue.suggested_action}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Action Footer */}
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "10px",
                paddingTop: "10px",
                borderTop: "1px solid #e2e8f0",
              }}
            >
              {(summary.unprocessed_count > 0 || totalIssuesCount > 0) &&
                onFilterIncomplete && (
                  <button
                    type="button"
                    data-testid="filter-incomplete-button"
                    onClick={() => {
                      onFilterIncomplete();
                      onClose();
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "8px 14px",
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#7c3aed",
                      backgroundColor: "#f5f3ff",
                      border: "1px solid #ddd6fe",
                      borderRadius: "6px",
                      cursor: "pointer",
                    }}
                  >
                    <Layers size={16} />
                    <span>Review Incomplete POIs</span>
                    <ArrowRight size={14} />
                  </button>
                )}

              <button
                type="button"
                data-testid="close-summary-button"
                onClick={onClose}
                style={{
                  padding: "8px 16px",
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "#ffffff",
                  backgroundColor: "#2563eb",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                Close Summary
              </button>
            </div>
          </>
        ) : null}
      </div>
    </Modal>
  );
};
