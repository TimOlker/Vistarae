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
import { apiFetch } from "../../services/api";
import { Loader2, CheckCircle2, AlertCircle, Layers, Clock, ArrowRight } from "lucide-react";

export interface IngestJobStatus {
  job_id: string;
  status?: "PENDING" | "PROCESSING" | "COMPLETED" | "PARTIAL_SUCCESS" | "FAILED";
  job_status?: "PENDING" | "PROCESSING" | "COMPLETED" | "PARTIAL_SUCCESS" | "FAILED";
  total_rows: number;
  processed_rows: number;
  duplicates_pending_count?: number;
  duplicate_payloads?: any[];
  error_message?: string;
}

interface CSVProgressModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenTriage: (jobId: string) => void;
  onJobComplete: () => void;
  onReupload?: () => void;
}

export const CSVProgressModal: React.FC<CSVProgressModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onOpenTriage,
  onJobComplete,
  onReupload,
}) => {
  const [job, setJob] = useState<IngestJobStatus | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [pollError, setPollError] = useState<string | null>(null);

  // Timer: Track elapsed seconds while modal is open
  useEffect(() => {
    if (!isOpen || !jobId) {
      setElapsedSeconds(0);
      setPollError(null);
      return;
    }

    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen, jobId]);

  // Polling loop for job status
  useEffect(() => {
    if (!isOpen || !jobId) return;

    let isMounted = true;

    const pollJob = async () => {
      try {
        const res = await apiFetch<IngestJobStatus>(
          `/api/ingest/jobs/${jobId}`,
        );
        if (!isMounted) return;
        setJob(res);
        setPollError(null);

        const currentStatus = res.status || res.job_status;
        const isFinished =
          currentStatus === "COMPLETED" ||
          currentStatus === "PARTIAL_SUCCESS" ||
          (res.total_rows > 0 && res.processed_rows >= res.total_rows);

        if (isFinished) {
          const dupCount = res.duplicates_pending_count ?? res.duplicate_payloads?.length ?? 0;
          if (dupCount > 0 || res.total_rows > 0) {
            onOpenTriage(jobId);
            onClose();
          } else {
            onJobComplete();
          }
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const errObj = err as { message?: string; problem?: { detail?: string } };
        const msg = errObj.problem?.detail || errObj.message || "Unable to reach ingestion service";
        setPollError(msg);
        console.error("Error polling ingest job:", err);
      }
    };

    pollJob();
    const interval = setInterval(pollJob, 1500); // 1.5-second polling interval

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [isOpen, jobId, onOpenTriage, onJobComplete, onClose]);

  if (!isOpen || !jobId) return null;

  const currentStatus = job?.status || job?.job_status;
  const percent =
    job && job.total_rows > 0
      ? Math.round((job.processed_rows / job.total_rows) * 100)
      : 0;

  const isCompleted =
    currentStatus === "COMPLETED" ||
    (job !== null && job.total_rows > 0 && job.processed_rows >= job.total_rows);
  const isFailed = currentStatus === "FAILED";

  const formatElapsed = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  const dupCount = job?.duplicates_pending_count ?? job?.duplicate_payloads?.length ?? 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Processing Ingestion Job"
      maxWidth="460px"
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          alignItems: "center",
          padding: "12px 0",
        }}
      >
        {isFailed ? (
          <AlertCircle size={44} color="var(--danger, #ef4444)" />
        ) : isCompleted ? (
          <CheckCircle2 size={44} color="var(--success, #10b981)" />
        ) : (
          <Loader2
            size={44}
            color="var(--accent, #2563eb)"
            className="spin"
            style={{ animation: "spin 1s linear infinite" }}
          />
        )}

        <div style={{ textAlign: "center" }}>
          <h4 style={{ fontSize: "16px", fontWeight: 700 }}>
            {isFailed
              ? "Ingestion Failed"
              : isCompleted
                ? "Ingestion Complete!"
                : "Processing Travel Records..."}
          </h4>
          <p
            style={{
              fontSize: "12px",
              color: "var(--text-muted)",
              marginTop: "4px",
            }}
          >
            Job ID: <code>{jobId}</code>
          </p>
        </div>

        {/* Progress Bar & Counters */}
        <div style={{ width: "100%" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "12px",
              marginBottom: "6px",
            }}
          >
            <span>Progress: {percent}%</span>
            <span>
              {job?.processed_rows || 0} / {job?.total_rows || 0} rows
            </span>
          </div>
          <div
            style={{
              width: "100%",
              height: "8px",
              borderRadius: "9999px",
              background: "var(--bg-hover, #e2e8f0)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${percent}%`,
                height: "100%",
                background: isCompleted ? "var(--success, #10b981)" : "var(--accent, #2563eb)",
                transition: "width 300ms ease",
              }}
            />
          </div>

          {/* Time Elapsed & Status Subtext */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: "8px",
              fontSize: "11px",
              color: "var(--text-muted)",
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
              <Clock size={12} />
              <span>Elapsed: <strong>{formatElapsed(elapsedSeconds)}</strong></span>
            </span>
            <span>
              {isCompleted
                ? "Ready for Phase 1 Triage"
                : percent === 100
                  ? "Finalizing..."
                  : elapsedSeconds > 10 && percent === 0
                    ? "Staging & analyzing duplicates..."
                    : "Active"}
            </span>
          </div>
        </div>

        {/* Polling Error Alert if Backend Unreachable */}
        {pollError && (
          <div
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "6px",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#b91c1c",
              fontSize: "12px",
            }}
          >
            Connection warning: {pollError}. Retrying...
          </div>
        )}

        {/* Duplicate Warning */}
        {dupCount > 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 14px",
              borderRadius: "8px",
              background: "#eff6ff",
              color: "#1d4ed8",
              fontSize: "12px",
              fontWeight: 600,
              width: "100%",
            }}
          >
            <Layers size={16} />
            <span>
              {dupCount} duplicate candidates awaiting triage
            </span>
          </div>
        )}

        {isFailed && (
          <p style={{ fontSize: "13px", color: "var(--danger)" }}>
            {job?.error_message ||
              "An error occurred during asynchronous CSV processing."}
          </p>
        )}

        {/* Action Buttons */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: "8px",
            width: "100%",
            marginTop: "8px",
          }}
        >
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
              border: "none",
              cursor: "pointer",
            }}
          >
            Close
          </button>

          {isCompleted ? (
            <button
              type="button"
              onClick={() => {
                onOpenTriage(jobId);
                onClose();
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--success, #10b981)",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor: "pointer",
              }}
            >
              <span>View Candidates</span>
              <ArrowRight size={14} />
            </button>
          ) : (
            onReupload && (
              <button
                type="button"
                onClick={onReupload}
                style={{
                  padding: "8px 16px",
                  borderRadius: "var(--radius-md, 8px)",
                  background: "var(--accent, #2563eb)",
                  color: "#ffffff",
                  fontWeight: 600,
                  fontSize: "13px",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Re-upload CSV
              </button>
            )
          )}
        </div>
      </div>
    </Modal>
  );
};
