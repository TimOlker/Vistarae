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

import React, { useEffect, useState, useRef } from "react";
import { Modal } from "../common/Modal";
import {
  ingestApi,
  type BulkEnrichmentProgressResult,
} from "../../services/ingestApi";
import {
  Sparkles,
  CheckCircle2,
  Clock,
  Cpu,
  AlertTriangle,
  StopCircle,
  Loader2,
} from "lucide-react";

export interface CSVEnrichmentProgressModalProps {
  jobId: string | null;
  isOpen: boolean;
  onComplete: () => void;
  onCancel?: () => void;
}

export const CSVEnrichmentProgressModal: React.FC<
  CSVEnrichmentProgressModalProps
> = ({ jobId, isOpen, onComplete, onCancel }) => {
  const [progress, setProgress] = useState<BulkEnrichmentProgressResult | null>(
    null,
  );
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isDraining, setIsDraining] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  // Local elapsed timer
  useEffect(() => {
    if (!isOpen || !jobId) {
      setElapsedSeconds(0);
      setProgress(null);
      setIsDraining(false);
      setCancelError(null);
      return;
    }

    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen, jobId]);

  // Heartbeat loop: 5-second interval while modal is active (REQ-ENR-032)
  // Uses a background Web Worker timer to prevent browser throttling when tab is not in the foreground.
  useEffect(() => {
    if (!isOpen || !jobId) return;

    const sendHeartbeat = async () => {
      try {
        await ingestApi.heartbeatBulkEnrichment(jobId);
      } catch (err: unknown) {
        console.warn("Bulk enrichment heartbeat failed:", err);
      }
    };

    let worker: Worker | null = null;
    let fallbackInterval: NodeJS.Timeout | null = null;

    try {
      if (typeof window !== "undefined" && window.Worker && window.Blob) {
        const workerScript = `
          let timer = null;
          self.onmessage = function(e) {
            if (e.data === 'start') {
              timer = setInterval(function() { self.postMessage('tick'); }, 5000);
            } else if (e.data === 'stop') {
              if (timer) clearInterval(timer);
            }
          };
        `;
        const blob = new Blob([workerScript], { type: "application/javascript" });
        const url = URL.createObjectURL(blob);
        worker = new Worker(url);
        worker.onmessage = () => {
          sendHeartbeat();
        };
        worker.postMessage("start");
      } else {
        fallbackInterval = setInterval(sendHeartbeat, 5000);
      }
    } catch {
      fallbackInterval = setInterval(sendHeartbeat, 5000);
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        sendHeartbeat();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (worker) {
        worker.postMessage("stop");
        worker.terminate();
      }
      if (fallbackInterval) {
        clearInterval(fallbackInterval);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isOpen, jobId]);

  // Polling loop for enrichment telemetry (REQ-ENR-022)
  useEffect(() => {
    if (!isOpen || !jobId) return;

    let isMounted = true;
    let pollInterval: NodeJS.Timeout;

    const poll = async () => {
      try {
        const res = await ingestApi.getBulkEnrichmentProgress(jobId);
        if (!isMounted || !res) return;
        setProgress(res);

        if (res.status === "DRAINING") {
          setIsDraining(true);
        }

        // Terminal states trigger completion transition
        const terminalStatuses = [
          "COMPLETED",
          "CANCELLED",
          "BLOCKED",
          "FAILED",
        ];
        if (terminalStatuses.includes(res.status)) {
          clearInterval(pollInterval);
          setTimeout(() => {
            if (isMounted) {
              onCompleteRef.current();
            }
          }, 600);
        }
      } catch (err: unknown) {
        console.warn("Bulk enrichment progress polling error:", err);
      }
    };

    poll();
    pollInterval = setInterval(poll, 1000);

    return () => {
      isMounted = false;
      clearInterval(pollInterval);
    };
  }, [isOpen, jobId]);

  const handleCancelClick = async () => {
    if (!jobId || isDraining) return;
    setIsDraining(true);
    setCancelError(null);
    try {
      await ingestApi.cancelBulkEnrichment(jobId);
    } catch (err: any) {
      console.error("Failed to cancel bulk enrichment:", err);
      setCancelError(err?.message || "Failed to trigger cancellation");
      setIsDraining(false);
    }
  };

  const percent = progress?.percent_complete ?? 0;
  const isFinished = progress?.status === "COMPLETED";
  const isTerminated =
    progress?.status &&
    ["COMPLETED", "CANCELLED", "BLOCKED", "FAILED"].includes(progress.status);

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        if (!isTerminated && !isDraining && onCancel) {
          onCancel();
        }
      }}
      title="AI Bulk POI Enrichment in Progress"
      maxWidth="580px"
    >
      <div
        data-testid="enrichment-progress-modal"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "18px",
          padding: "8px 4px",
          color: "#1e293b",
        }}
      >
        {/* Banner with icon and animated status indicator */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "14px",
            padding: "14px 16px",
            backgroundColor: isDraining
              ? "#fffbeb"
              : isFinished
                ? "#f0fdf4"
                : "#faf5ff",
            border: `1px solid ${
              isDraining ? "#fde68a" : isFinished ? "#bbf7d0" : "#e9d5ff"
            }`,
            borderRadius: "10px",
          }}
        >
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              backgroundColor: isDraining
                ? "#fef3c7"
                : isFinished
                  ? "#dcfce7"
                  : "#f3e8ff",
              border: `1px solid ${
                isDraining ? "#fcd34d" : isFinished ? "#86efac" : "#d8b4fe"
              }`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {isFinished ? (
              <CheckCircle2 size={24} color="#16a34a" />
            ) : isDraining ? (
              <Loader2 size={22} color="#d97706" className="animate-spin" />
            ) : (
              <Sparkles size={22} color="#9333ea" />
            )}
          </div>
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontWeight: 700,
                fontSize: "14px",
                color: isDraining
                  ? "#92400e"
                  : isFinished
                    ? "#166534"
                    : "#581c87",
              }}
            >
              {isFinished
                ? "Enrichment Complete!"
                : isDraining
                  ? "Cancellation Requested — Draining Active Workers"
                  : progress?.status === "CANARY_DISPATCH"
                    ? "Canary Extraction Dispatch (Candidate #1)"
                    : "Parallel AI & Web Enrichment Active"}
            </div>
            <div
              style={{
                fontSize: "12px",
                color: isDraining
                  ? "#b45309"
                  : isFinished
                    ? "#15803d"
                    : "#6b21a8",
                marginTop: "2px",
              }}
            >
              {isDraining
                ? "Allowing in-flight AI queries to complete cleanly (up to 30s)..."
                : progress?.status_message || "Initializing workers..."}
            </div>
          </div>
        </div>

        {/* Progress Bar Container */}
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "8px",
              fontSize: "12px",
              fontWeight: 600,
              color: "#475569",
            }}
          >
            <span>
              {progress?.total_count
                ? `Processed ${progress.completed_count} of ${progress.total_count} candidates`
                : "Queueing candidates..."}
            </span>
            <span style={{ color: "#7c3aed", fontWeight: 700 }}>
              {percent}%
            </span>
          </div>

          <div
            style={{
              width: "100%",
              height: "10px",
              backgroundColor: "#e2e8f0",
              borderRadius: "999px",
              overflow: "hidden",
            }}
          >
            <div
              data-testid="enrichment-progress-bar"
              style={{
                width: `${percent}%`,
                height: "100%",
                background: isDraining
                  ? "linear-gradient(90deg, #f59e0b 0%, #d97706 100%)"
                  : "linear-gradient(90deg, #9333ea 0%, #3b82f6 100%)",
                borderRadius: "999px",
                transition: "width 300ms ease-in-out",
              }}
            />
          </div>
        </div>

        {/* Telemetry Metrics Grid (REQ-ENR-022) */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: "10px",
            fontSize: "12px",
          }}
        >
          <div
            style={{
              padding: "10px 12px",
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
              Completed / Queued
            </div>
            <div
              style={{
                fontWeight: 700,
                color: "#1e293b",
                fontSize: "14px",
                marginTop: "2px",
              }}
            >
              {progress?.completed_count ?? 0} / {progress?.total_count ?? 0}
            </div>
            <div
              style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}
            >
              Remaining: {progress?.remaining_count ?? 0}
            </div>
          </div>

          <div
            style={{
              padding: "10px 12px",
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
              In-Flight Workers
            </div>
            <div
              style={{
                fontWeight: 700,
                color: "#2563eb",
                fontSize: "14px",
                marginTop: "2px",
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <Cpu size={16} />
              {progress?.in_flight_count ?? 0} active
            </div>
            <div
              style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}
            >
              Issues: {progress?.issue_count ?? 0}
            </div>
          </div>

          <div
            style={{
              padding: "10px 12px",
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
              Elapsed Time
            </div>
            <div
              style={{
                fontWeight: 700,
                color: "#1e293b",
                fontSize: "14px",
                marginTop: "2px",
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <Clock size={16} color="#64748b" />
              {elapsedSeconds}s
            </div>
            <div
              style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}
            >
              Avg:{" "}
              {progress?.average_duration_ms
                ? `${(progress.average_duration_ms / 1000).toFixed(1)}s/POI`
                : "--"}
            </div>
          </div>
        </div>

        {/* Error notification if cancel call failed */}
        {cancelError && (
          <div
            style={{
              fontSize: "12px",
              color: "#b91c1c",
              backgroundColor: "#fef2f2",
              padding: "8px 12px",
              borderRadius: "6px",
              border: "1px solid #fecaca",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <AlertTriangle size={16} />
            <span>{cancelError}</span>
          </div>
        )}

        {/* Interactive Cancellation Footer (REQ-ENR-021) */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            paddingTop: "6px",
            borderTop: "1px solid #e2e8f0",
          }}
        >
          <div style={{ fontSize: "11px", color: "#64748b" }}>
            Heartbeat active (5s keepalive)
          </div>
          <button
            type="button"
            data-testid="cancel-enrichment-button"
            disabled={
              isDraining || isTerminated || progress?.can_cancel === false
            }
            onClick={handleCancelClick}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 14px",
              fontSize: "13px",
              fontWeight: 600,
              color: isDraining || isTerminated ? "#94a3b8" : "#dc2626",
              backgroundColor:
                isDraining || isTerminated ? "#f1f5f9" : "#fef2f2",
              border: `1px solid ${
                isDraining || isTerminated ? "#cbd5e1" : "#fca5a5"
              }`,
              borderRadius: "6px",
              cursor: isDraining || isTerminated ? "not-allowed" : "pointer",
              transition: "all 150ms ease",
            }}
          >
            {isDraining ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Draining...</span>
              </>
            ) : (
              <>
                <StopCircle size={16} />
                <span>Cancel Enrichment</span>
              </>
            )}
          </button>
        </div>
      </div>
    </Modal>
  );
};
