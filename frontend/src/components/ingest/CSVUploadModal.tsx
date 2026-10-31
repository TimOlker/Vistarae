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

import React, { useState, useEffect, useRef } from "react";
import { Modal } from "../common/Modal";
import { SplitModal } from "./SplitModal";
import { useToast } from "../../context/ToastContext";
import { apiFetch } from "../../services/api";
import { ingestApi, type ActiveSessionResult } from "../../services/ingestApi";
import {
  UploadCloud,
  FileSpreadsheet,
  ArrowRight,
  Loader2,
  AlertCircle,
  AlertTriangle,
  Clock,
  RotateCw,
} from "lucide-react";

interface CSVUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onJobCreated: (jobId: string) => void;
  onResumeJob?: (jobId: string, phase: "phase_1_triage" | "phase_2_enriched") => void;
}

export const CSVUploadModal: React.FC<CSVUploadModalProps> = ({
  isOpen,
  onClose,
  onJobCreated,
  onResumeJob,
}) => {
  const { showToast } = useToast();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [targetListName, setTargetListName] = useState("");
  const [existingLists, setExistingLists] = useState<Array<{ id: string; title: string }>>([]);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [uploadError, setUploadError] = useState<{ title: string; detail: string } | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Active Session Resume & Overwrite States
  const [activeSession, setActiveSession] = useState<ActiveSessionResult | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [showOverwriteWarning, setShowOverwriteWarning] = useState(false);
  const [isWipingSession, setIsWipingSession] = useState(false);

  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    if (isUploading) {
      setElapsedSeconds(0);
      setUploadError(null);
      timer = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isUploading]);

  useEffect(() => {
    if (!isOpen) {
      setShowOverwriteWarning(false);
      setSelectedFile(null);
      setUploadError(null);
      return;
    }
    const fetchLists = async () => {
      try {
        const lists = await apiFetch<Array<{ id: string; title: string }>>("/api/lists");
        if (Array.isArray(lists)) {
          setExistingLists(lists);
        }
      } catch {
        // Silently ignore if lists fail to fetch
      }
    };

    const fetchActiveSession = async () => {
      setIsLoadingSession(true);
      try {
        const session = await ingestApi.getActiveSession();
        setActiveSession(session.has_active_session ? session : null);
      } catch {
        setActiveSession(null);
      } finally {
        setIsLoadingSession(false);
      }
    };

    fetchLists();
    fetchActiveSession();
  }, [isOpen]);

  const handleResume = () => {
    if (activeSession && activeSession.job_id && activeSession.phase_state) {
      if (onResumeJob) {
        onResumeJob(activeSession.job_id, activeSession.phase_state);
      }
      onClose();
    }
  };

  const handleDiscardActiveSession = async () => {
    if (
      typeof window !== "undefined" &&
      typeof window.confirm === "function"
    ) {
      try {
        if (
          !window.confirm(
            "Are you sure you want to discard the previous in-progress import? All temporary staged changes will be wiped.",
          )
        ) {
          return;
        }
      } catch {
        // Fallback if window.confirm fails
      }
    }
    setIsWipingSession(true);
    try {
      await ingestApi.wipeActiveSession();
      setActiveSession(null);
      showToast("Previous import session cleared.", "info");
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      showToast(`Failed to clear session: ${errObj?.message || "Unknown error"}`, "error");
    } finally {
      setIsWipingSession(false);
    }
  };

  // SplitModal state
  const [isSplitModalOpen, setIsSplitModalOpen] = useState(false);
  const [splitDetails, setSplitDetails] = useState({
    fileName: "",
    fileSizeBytes: 0,
    rowCount: 0,
  });

  const handleFileChange = async (file: File) => {
    setSelectedFile(file);

    // Fast client-side line count inspection
    const text = typeof file.text === "function" ? await file.text() : "";
    const rows =
      text.split(/\r\n|\n/).filter((line) => line.trim().length > 0).length - 1; // subtract header

    const isOverSize = file.size > 2 * 1024 * 1024;
    const isOverRows = rows > 2000;

    if (isOverSize || isOverRows) {
      setSplitDetails({
        fileName: file.name,
        fileSizeBytes: file.size,
        rowCount: Math.max(0, rows),
      });
      setIsSplitModalOpen(true);
      setSelectedFile(null);
    }
  };

  const executeUpload = async () => {
    if (!selectedFile) return;

    setShowOverwriteWarning(false);
    setUploadError(null);
    setIsUploading(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      if (targetListName.trim()) {
        formData.append("target_list_name", targetListName.trim());
      }

      const res = await apiFetch<{ job_id: string }>("/api/ingest/upload", {
        method: "POST",
        body: formData,
        signal: abortController.signal,
        timeoutMs: 600000, // 10 minutes for processing, geocaching & staging
      });

      showToast(`Upload accepted! Job ID: ${res.job_id}`, "success");
      onJobCreated(res.job_id);
      onClose();
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      const title = errorObj.problem?.title || "Upload Failed";
      const detail =
        errorObj.problem?.detail ||
        errorObj.message ||
        "Failed to upload and stage CSV file. Please verify backend status and try again.";
      setUploadError({ title, detail });
      showToast({ title, detail }, "error");
    } finally {
      setIsUploading(false);
      abortControllerRef.current = null;
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    if (activeSession?.has_active_session) {
      setShowOverwriteWarning(true);
      return;
    }

    await executeUpload();
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title="Import Travel Points (CSV)"
        maxWidth="500px"
      >
        {isUploading ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              padding: "12px 4px",
              textAlign: "center",
            }}
          >
            <div style={{ display: "flex", justifyContent: "center", margin: "8px 0" }}>
              <Loader2 size={40} color="var(--accent, #2563eb)" className="animate-spin" />
            </div>

            <div>
              <h3
                style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "var(--text-primary, #0f172a)",
                  margin: "0 0 6px 0",
                }}
              >
                Uploading & Staging Travel Records...
              </h3>
              <p style={{ fontSize: "12px", color: "var(--text-muted, #64748b)", margin: 0 }}>
                {selectedFile?.name} (
                {((selectedFile?.size || 0) / 1024).toFixed(1)} KB)
              </p>
            </div>

            {/* Dynamic Progress Bar */}
            <div
              style={{
                width: "100%",
                backgroundColor: "#e2e8f0",
                borderRadius: "9999px",
                height: "10px",
                overflow: "hidden",
                marginTop: "4px",
              }}
            >
              <div
                style={{
                  height: "100%",
                  borderRadius: "9999px",
                  backgroundColor: "var(--accent, #2563eb)",
                  width: `${Math.min(95, Math.max(12, elapsedSeconds * 7))}%`,
                  transition: "width 0.4s ease-out",
                }}
              />
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                fontSize: "11px",
                color: "var(--text-muted, #64748b)",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "4px", fontWeight: 600 }}>
                <Clock size={12} />
                Elapsed: {Math.floor(elapsedSeconds / 60)}:
                {(elapsedSeconds % 60).toString().padStart(2, "0")}
              </span>
              <span style={{ fontStyle: "italic" }}>
                {elapsedSeconds < 3
                  ? "Transferring CSV payload..."
                  : elapsedSeconds < 8
                  ? "Validating schema & checking geocache..."
                  : "Staging candidates & resolving coordinates..."}
              </span>
            </div>

            <div
              style={{
                fontSize: "11px",
                color: "#64748b",
                backgroundColor: "#f8fafc",
                border: "1px solid #e2e8f0",
                padding: "8px 12px",
                borderRadius: "6px",
                textAlign: "left",
                lineHeight: "1.4",
              }}
            >
              ℹ️ Missing coordinates are being forward-geocoded against OpenStreetMap (cached entries resolve immediately; uncached queries throttle at 1/sec).
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "4px" }}>
              <button
                type="button"
                onClick={() => {
                  if (abortControllerRef.current) {
                    abortControllerRef.current.abort();
                  }
                  setIsUploading(false);
                }}
                style={{
                  padding: "6px 14px",
                  borderRadius: "var(--radius-md, 6px)",
                  background: "#f1f5f9",
                  color: "#64748b",
                  fontWeight: 600,
                  fontSize: "12px",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Cancel Upload
              </button>
            </div>
          </div>
        ) : (
          <form
            onSubmit={handleUpload}
            style={{ display: "flex", flexDirection: "column", gap: "16px" }}
          >
            {uploadError && (
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  padding: "12px",
                  borderRadius: "8px",
                  backgroundColor: "#fef2f2",
                  border: "1px solid #fca5a5",
                  color: "#991b1b",
                  fontSize: "12px",
                  lineHeight: "1.4",
                }}
              >
                <AlertCircle size={18} style={{ flexShrink: 0, marginTop: "2px", color: "#dc2626" }} />
                <div style={{ flex: 1, textAlign: "left" }}>
                  <div style={{ fontWeight: 700, marginBottom: "2px" }}>
                    {uploadError.title}
                  </div>
                  <div>{uploadError.detail}</div>
                </div>
                <button
                  type="button"
                  onClick={() => setUploadError(null)}
                  style={{
                    border: "none",
                    background: "transparent",
                    color: "#991b1b",
                    cursor: "pointer",
                    fontWeight: 700,
                    fontSize: "14px",
                    lineHeight: 1,
                  }}
                  title="Dismiss error"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Active Session Detected Card */}
            {activeSession?.has_active_session && (
              <div
                data-testid="active-session-card"
                style={{
                  padding: "12px 14px",
                  borderRadius: "8px",
                  backgroundColor: "#eff6ff",
                  border: "1px solid #bfdbfe",
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  textAlign: "left",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <Clock size={16} color="#2563eb" />
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: "13px",
                        color: "#1e40af",
                      }}
                    >
                      In-Progress Import Detected
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: "9999px",
                      backgroundColor: "#dbeafe",
                      color: "#1e40af",
                    }}
                  >
                    {activeSession.phase_state === "phase_2_enriched"
                      ? "Phase 2: Review & Commit"
                      : "Phase 1: Validation & Triage"}
                  </span>
                </div>

                <p
                  style={{
                    margin: 0,
                    fontSize: "12px",
                    color: "#1e3a8a",
                    lineHeight: 1.4,
                  }}
                >
                  You have a saved temporary session with{" "}
                  <strong>{activeSession.total_candidates}</strong> POIs staged in
                  the database
                  {activeSession.target_list_name
                    ? ` (assigned to list "${activeSession.target_list_name}")`
                    : ""}
                  . You can resume right where you left off.
                </p>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginTop: "4px",
                  }}
                >
                  <button
                    type="button"
                    onClick={handleResume}
                    data-testid="resume-import-button"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "6px 14px",
                      borderRadius: "6px",
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      fontSize: "12px",
                      fontWeight: 600,
                      border: "none",
                      cursor: "pointer",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                    }}
                  >
                    <span>Resume Import</span>
                    <ArrowRight size={13} />
                  </button>

                  <button
                    type="button"
                    onClick={handleDiscardActiveSession}
                    disabled={isWipingSession}
                    data-testid="discard-active-session-button"
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      backgroundColor: "transparent",
                      color: "#b91c1c",
                      fontSize: "12px",
                      fontWeight: 500,
                      border: "1px solid #fecaca",
                      cursor: isWipingSession ? "not-allowed" : "pointer",
                    }}
                  >
                    {isWipingSession ? "Clearing..." : "Discard Session"}
                  </button>
                </div>
              </div>
            )}

            <div
              style={{
                border: "2px dashed var(--border-color, #cbd5e1)",
                borderRadius: "var(--radius-md, 10px)",
                padding: "24px 16px",
                textAlign: "center",
                background: "var(--bg-hover, #f8fafc)",
                cursor: "pointer",
                position: "relative",
              }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                  handleFileChange(e.dataTransfer.files[0]);
                }
              }}
            >
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileChange(e.target.files[0]);
                  }
                }}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "100%",
                  opacity: 0,
                  cursor: "pointer",
                }}
              />

              {selectedFile ? (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                    textAlign: "left",
                  }}
                >
                  <FileSpreadsheet size={32} color="var(--success, #10b981)" />
                  <div>
                    <p style={{ fontSize: "13px", fontWeight: 600 }}>
                      {selectedFile.name}
                    </p>
                    <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      {(selectedFile.size / 1024).toFixed(1)} KB • Validated
                      within guardrails
                    </p>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <UploadCloud size={32} color="var(--accent, #2563eb)" />
                  <p style={{ fontSize: "14px", fontWeight: 600 }}>
                    Select or drag a CSV file here
                  </p>
                  <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    Max 2.0 MB • Max 2,000 rows • Automatic duplicate triage
                  </p>
                </div>
              )}
            </div>

            {/* Optional Target List Input */}
            <div style={{ textAlign: "left" }}>
              <label
                htmlFor="target-list-input"
                style={{
                  display: "block",
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "#334155",
                  marginBottom: "4px",
                }}
              >
                Assign to List (Optional):
              </label>
              <input
                id="target-list-input"
                data-testid="target-list-input"
                type="text"
                list="existing-lists-datalist"
                value={targetListName}
                onChange={(e) => setTargetListName(e.target.value)}
                placeholder="Select or enter a list name (e.g. London 2025)..."
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  fontSize: "13px",
                  border: "1px solid #cbd5e1",
                  borderRadius: "6px",
                  outline: "none",
                  backgroundColor: "#ffffff",
                  color: "#0f172a",
                }}
              />
              <datalist id="existing-lists-datalist">
                {existingLists.map((l) => (
                  <option key={l.id} value={l.title} />
                ))}
              </datalist>
              <p style={{ fontSize: "11px", color: "#64748b", margin: "4px 0 0 0" }}>
                When specified, all non-ignored POIs will be added to this list upon import.
              </p>
            </div>

            <div
              style={{
                fontSize: "12px",
                color: "var(--text-secondary)",
                background: "var(--bg-hover)",
                padding: "10px",
                borderRadius: "6px",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                textAlign: "left",
              }}
            >
              <div>
                <strong>Supported CSV Formats:</strong>
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", lineHeight: "1.4" }}>
                • <strong>Photo Scraper & Standard POI Export:</strong>{" "}
                <code>
                  POI Name, Street Address, Town/City, State/Province, Zip Code, Country, latitude, longitude, dates visited, Photo directory, location_confidence_percent, confidence_source, Tags
                </code>
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", lineHeight: "1.4" }}>
                • <strong>Generic CSV:</strong>{" "}
                <code>name, latitude, longitude, city, rating, tags</code>
              </div>
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "8px",
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
                Cancel
              </button>
              <button
                type="submit"
                disabled={!selectedFile || isUploading}
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
                    !selectedFile || isUploading ? "not-allowed" : "pointer",
                  opacity: !selectedFile || isUploading ? 0.6 : 1,
                }}
              >
                <span>{isUploading ? "Uploading..." : "Start Ingestion"}</span>
                <ArrowRight size={14} />
              </button>
            </div>
          </form>
        )}
      </Modal>

      <SplitModal
        isOpen={isSplitModalOpen}
        onClose={() => setIsSplitModalOpen(false)}
        fileName={splitDetails.fileName}
        fileSizeBytes={splitDetails.fileSizeBytes}
        rowCount={splitDetails.rowCount}
      />

      {/* Overwrite Confirmation Warning Modal */}
      {showOverwriteWarning && (
        <Modal
          isOpen={true}
          onClose={() => setShowOverwriteWarning(false)}
          title="Overwrite Active Import Progress?"
          maxWidth="460px"
        >
          <div
            data-testid="overwrite-warning-modal"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "14px",
              textAlign: "left",
            }}
          >
            <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
              <AlertTriangle
                size={26}
                color="#dc2626"
                style={{ flexShrink: 0, marginTop: "2px" }}
              />
              <div>
                <h4
                  style={{
                    margin: "0 0 6px 0",
                    fontSize: "14px",
                    fontWeight: 700,
                    color: "#0f172a",
                  }}
                >
                  Previous Import Progress Will Be Wiped Out
                </h4>
                <p
                  style={{
                    margin: 0,
                    fontSize: "12px",
                    color: "#475569",
                    lineHeight: 1.5,
                  }}
                >
                  You already have an active import session containing{" "}
                  <strong>{activeSession?.total_candidates}</strong> candidate POIs
                  staged at{" "}
                  <strong>
                    {activeSession?.phase_state === "phase_2_enriched"
                      ? "Phase 2 (Review & Commit)"
                      : "Phase 1 (Validation & Triage)"}
                  </strong>
                  .
                </p>
                <p
                  style={{
                    margin: "8px 0 0 0",
                    fontSize: "12px",
                    color: "#b91c1c",
                    fontWeight: 600,
                    lineHeight: 1.4,
                  }}
                >
                  Importing a new CSV file will discard and overwrite this previous
                  progress. Do you wish to continue?
                </p>
              </div>
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "8px",
                marginTop: "6px",
              }}
            >
              <button
                type="button"
                onClick={() => setShowOverwriteWarning(false)}
                data-testid="cancel-overwrite-button"
                style={{
                  padding: "8px 14px",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  backgroundColor: "#ffffff",
                  color: "#334155",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Cancel & Resume Saved Import
              </button>
              <button
                type="button"
                onClick={executeUpload}
                data-testid="confirm-overwrite-button"
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor: "#dc2626",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Wipe & Start New Import
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
};
