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

import React, { useState } from "react";
import { Modal } from "./Modal";
import {
  ingestApi,
  type BulkEnrichmentRecoveryResult,
} from "../../services/ingestApi";
import { AlertTriangle, Play, Check, X, Loader2 } from "lucide-react";

export interface BulkEnrichmentRecoveryModalProps {
  isOpen: boolean;
  recoveryRun: BulkEnrichmentRecoveryResult | null;
  onResume: (jobId: string, initialFilter: string) => void;
  onDismiss: () => void;
  onClose: () => void;
}

export const BulkEnrichmentRecoveryModal: React.FC<
  BulkEnrichmentRecoveryModalProps
> = ({ isOpen, recoveryRun, onResume, onDismiss, onClose }) => {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!recoveryRun) return null;

  const handleAction = async (action: "resume" | "dismiss" | "cancel") => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await ingestApi.respondBulkEnrichmentRecovery({
        result_id: recoveryRun.result_id,
        action,
      });

      if (action === "resume") {
        onResume(res.job_id, res.initial_filter || "incomplete");
      } else if (action === "dismiss") {
        onDismiss();
      } else {
        onClose();
      }
    } catch (err: any) {
      console.error("Failed to respond to recovery prompt:", err);
      setError(err?.message || "Failed to process selection");
    } finally {
      setSubmitting(false);
    }
  };

  const formattedDate = recoveryRun.failed_at
    ? new Date(recoveryRun.failed_at).toLocaleString()
    : "recently";

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => handleAction("cancel")}
      title="Interrupted AI Enrichment Session"
      maxWidth="560px"
    >
      <div
        data-testid="bulk-enrichment-recovery-modal"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          padding: "6px 2px",
          color: "#1e293b",
        }}
      >
        {/* Banner with Alert */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "14px",
            padding: "14px 16px",
            backgroundColor: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: "10px",
          }}
        >
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "50%",
              backgroundColor: "#fef3c7",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <AlertTriangle size={22} color="#d97706" />
          </div>
          <div>
            <div
              style={{ fontWeight: 700, fontSize: "14px", color: "#92400e" }}
            >
              Previous Bulk Enrichment Did Not Complete
            </div>
            <div
              style={{ fontSize: "12px", color: "#b45309", marginTop: "2px" }}
            >
              A batch AI enrichment session from {formattedDate} was interrupted
              with {recoveryRun.unprocessed_count} unenriched candidates
              remaining.
            </div>
          </div>
        </div>

        {/* Itemized run details */}
        <div
          style={{
            padding: "12px 14px",
            backgroundColor: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            fontSize: "12px",
            lineHeight: "1.6",
          }}
        >
          <div>
            <strong>Interruption Reason:</strong>{" "}
            <span style={{ color: "#b91c1c" }}>
              {recoveryRun.termination_reason || "External service error"}
            </span>
          </div>
          <div style={{ marginTop: "4px" }}>
            <strong>Remaining Unenriched POIs:</strong>{" "}
            <span>
              {recoveryRun.unprocessed_count} of {recoveryRun.total_candidates}
            </span>
          </div>
        </div>

        {error && (
          <div
            style={{
              padding: "10px 12px",
              backgroundColor: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: "6px",
              color: "#991b1b",
              fontSize: "12px",
            }}
          >
            {error}
          </div>
        )}

        <div style={{ fontSize: "13px", color: "#475569" }}>
          Would you like to resume processing your remaining incomplete POIs
          now?
        </div>

        {/* Action Buttons (REQ-ENR-035) */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "8px",
            paddingTop: "10px",
            borderTop: "1px solid #e2e8f0",
          }}
        >
          <button
            type="button"
            data-testid="recovery-cancel-button"
            disabled={submitting}
            onClick={() => handleAction("cancel")}
            style={{
              padding: "8px 12px",
              fontSize: "13px",
              fontWeight: 500,
              color: "#64748b",
              backgroundColor: "#f8fafc",
              border: "1px solid #cbd5e1",
              borderRadius: "6px",
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            Decide Later
          </button>

          <button
            type="button"
            data-testid="recovery-dismiss-button"
            disabled={submitting}
            onClick={() => handleAction("dismiss")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: "8px 12px",
              fontSize: "13px",
              fontWeight: 500,
              color: "#334155",
              backgroundColor: "#f1f5f9",
              border: "1px solid #cbd5e1",
              borderRadius: "6px",
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            <X size={15} />
            <span>No, Dismiss</span>
          </button>

          <button
            type="button"
            data-testid="recovery-resume-button"
            disabled={submitting}
            onClick={() => handleAction("resume")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 16px",
              fontSize: "13px",
              fontWeight: 600,
              color: "#ffffff",
              backgroundColor: "#7c3aed",
              border: "none",
              borderRadius: "6px",
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            {submitting ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Play size={15} />
            )}
            <span>Yes, Resume Processing</span>
          </button>
        </div>
      </div>
    </Modal>
  );
};
