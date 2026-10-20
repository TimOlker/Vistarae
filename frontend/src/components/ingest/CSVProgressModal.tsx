// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useState } from "react";
import { Modal } from "../common/Modal";
import { apiFetch } from "../../services/api";
import { Loader2, CheckCircle2, AlertCircle, Layers } from "lucide-react";

export interface IngestJobStatus {
  job_id: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "PARTIAL_SUCCESS" | "FAILED";
  total_rows: number;
  processed_rows: number;
  duplicates_pending_count: number;
  error_message?: string;
}

interface CSVProgressModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenTriage: (jobId: string) => void;
  onJobComplete: () => void;
}

export const CSVProgressModal: React.FC<CSVProgressModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onOpenTriage,
  onJobComplete,
}) => {
  const [job, setJob] = useState<IngestJobStatus | null>(null);

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

        if (res.status === "COMPLETED" || res.status === "PARTIAL_SUCCESS") {
          if (res.duplicates_pending_count > 0) {
            onOpenTriage(jobId);
            onClose();
          } else {
            onJobComplete();
          }
        }
      } catch (err) {
        console.error("Error polling ingest job:", err);
      }
    };

    pollJob();
    const interval = setInterval(pollJob, 2000); // 2-second polling interval

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [isOpen, jobId, onOpenTriage, onJobComplete, onClose]);

  if (!isOpen || !jobId) return null;

  const percent =
    job && job.total_rows > 0
      ? Math.round((job.processed_rows / job.total_rows) * 100)
      : 0;

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
        {job?.status === "FAILED" ? (
          <AlertCircle size={44} color="var(--danger, #ef4444)" />
        ) : job?.status === "COMPLETED" ? (
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
            {job?.status === "FAILED"
              ? "Ingestion Failed"
              : job?.status === "COMPLETED"
                ? "Ingestion Complete"
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

        {/* Progress Bar */}
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
                background: "var(--accent, #2563eb)",
                transition: "width 300ms ease",
              }}
            />
          </div>
        </div>

        {/* Duplicate Warning */}
        {job && job.duplicates_pending_count > 0 && (
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
              {job.duplicates_pending_count} duplicate candidates awaiting
              triage
            </span>
          </div>
        )}

        {job?.status === "FAILED" && (
          <p style={{ fontSize: "13px", color: "var(--danger)" }}>
            {job.error_message ||
              "An error occurred during asynchronous CSV processing."}
          </p>
        )}

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
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
            }}
          >
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
};
