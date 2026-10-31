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
import { ingestApi, type Phase2ProgressResult } from "../../services/ingestApi";
import { Sparkles, CheckCircle2, Clock, Globe } from "lucide-react";

export interface CSVEnrichmentProgressModalProps {
  jobId: string | null;
  isOpen: boolean;
  onComplete: () => void;
  onCancel?: () => void;
}

export const CSVEnrichmentProgressModal: React.FC<CSVEnrichmentProgressModalProps> = ({
  jobId,
  isOpen,
  onComplete,
  onCancel,
}) => {
  const [progress, setProgress] = useState<Phase2ProgressResult | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Timer: Track elapsed seconds while active
  useEffect(() => {
    if (!isOpen || !jobId) {
      setElapsedSeconds(0);
      setProgress(null);
      return;
    }

    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen, jobId]);

  // Polling loop for enrichment progress
  useEffect(() => {
    if (!isOpen || !jobId) return;

    let isMounted = true;
    let pollInterval: NodeJS.Timeout;

    const poll = async () => {
      try {
        const res = await ingestApi.getPhase2Progress(jobId);
        if (!isMounted) return;
        setProgress(res);

        if (res.is_complete || (res.total_count > 0 && res.enriched_count >= res.total_count)) {
          clearInterval(pollInterval);
          setTimeout(() => {
            if (isMounted) {
              onComplete();
            }
          }, 600);
        }
      } catch {
        // Keep polling on transient failure
      }
    };

    poll();
    pollInterval = setInterval(poll, 800);

    return () => {
      isMounted = false;
      clearInterval(pollInterval);
    };
  }, [isOpen, jobId, onComplete]);

  const percent = progress?.percent_complete ?? 0;
  const isFinished = progress?.is_complete ?? false;

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {
        if (onCancel) onCancel();
      }}
      title="AI & Web Enrichment in Progress"
      maxWidth="560px"
    >
      <div
        data-testid="enrichment-progress-modal"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          padding: "8px 4px",
          color: "#1e293b",
        }}
      >
        {/* Banner with icon and animated indicator */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "14px",
            padding: "14px 16px",
            backgroundColor: "#faf5ff",
            border: "1px solid #e9d5ff",
            borderRadius: "10px",
          }}
        >
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              backgroundColor: "#f3e8ff",
              border: "1px solid #d8b4fe",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {isFinished ? (
              <CheckCircle2 size={24} color="#16a34a" />
            ) : (
              <Sparkles size={22} color="#9333ea" />
            )}
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: "14px", color: "#581c87" }}>
              {isFinished ? "Enrichment Complete!" : "Parallel POI Synthesis & Web Discovery"}
            </div>
            <div style={{ fontSize: "12px", color: "#6b21a8", marginTop: "2px" }}>
              {progress?.status_message || "Synthesizing AI summaries, Wikipedia, hero photos, and durations..."}
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
                ? `Enriched ${progress.enriched_count} of ${progress.total_count} candidates`
                : "Queueing parallel tasks..."}
            </span>
            <span style={{ color: "#7c3aed", fontWeight: 700 }}>{percent}%</span>
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
                background: "linear-gradient(90deg, #9333ea 0%, #3b82f6 100%)",
                borderRadius: "999px",
                transition: "width 300ms ease-in-out",
              }}
            />
          </div>
        </div>

        {/* Status Metrics */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
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
              display: "flex",
              alignItems: "center",
              gap: "8px",
              color: "#475569",
            }}
          >
            <Clock size={16} color="#64748b" />
            <div>
              <div style={{ fontSize: "10px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 700 }}>
                Elapsed Time
              </div>
              <div style={{ fontWeight: 600, color: "#1e293b" }}>{elapsedSeconds}s</div>
            </div>
          </div>

          <div
            style={{
              padding: "10px 12px",
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              color: "#475569",
            }}
          >
            <Globe size={16} color="#64748b" />
            <div>
              <div style={{ fontSize: "10px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 700 }}>
                Workers
              </div>
              <div style={{ fontWeight: 600, color: "#1e293b" }}>Parallel Concurrent</div>
            </div>
          </div>
        </div>

        {/* Information Callout */}
        <div
          style={{
            fontSize: "11px",
            color: "#64748b",
            lineHeight: "1.4",
            padding: "8px 12px",
            backgroundColor: "#f1f5f9",
            borderRadius: "6px",
          }}
        >
          ℹ️ <strong>What’s being computed in parallel:</strong>
          <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
            <li>Official attraction websites & Wikipedia articles</li>
            <li>High-resolution hero photo thumbnails</li>
            <li>Recommended visit durations & itinerary days</li>
            <li>Tailored travel reasoning & approved category tags</li>
          </ul>
        </div>
      </div>
    </Modal>
  );
};

