// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState } from "react";
import { Modal } from "../common/Modal";
import { SplitModal } from "./SplitModal";
import { useToast } from "../../context/ToastContext";
import { apiFetch } from "../../services/api";
import { UploadCloud, FileSpreadsheet, ArrowRight } from "lucide-react";

interface CSVUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onJobCreated: (jobId: string) => void;
}

export const CSVUploadModal: React.FC<CSVUploadModalProps> = ({
  isOpen,
  onClose,
  onJobCreated,
}) => {
  const { showToast } = useToast();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

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
    const text = await file.text();
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

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await apiFetch<{ job_id: string }>("/api/ingest/upload", {
        method: "POST",
        body: formData,
      });

      showToast(`Upload accepted! Job ID: ${res.job_id}`, "success");
      onJobCreated(res.job_id);
      onClose();
    } catch (err: unknown) {
      const errorObj = err as {
        problem?: { title: string; detail: string };
        message?: string;
      };
      showToast(errorObj.problem || errorObj.message || "CSV upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title="Import Travel Points (CSV)"
        maxWidth="500px"
      >
        <form
          onSubmit={handleUpload}
          style={{ display: "flex", flexDirection: "column", gap: "16px" }}
        >
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

          <div
            style={{
              fontSize: "12px",
              color: "var(--text-secondary)",
              background: "var(--bg-hover)",
              padding: "10px",
              borderRadius: "6px",
            }}
          >
            <strong>Expected CSV headers:</strong>{" "}
            <code>name, latitude, longitude, city, rating, tags</code>
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
      </Modal>

      <SplitModal
        isOpen={isSplitModalOpen}
        onClose={() => setIsSplitModalOpen(false)}
        fileName={splitDetails.fileName}
        fileSizeBytes={splitDetails.fileSizeBytes}
        rowCount={splitDetails.rowCount}
      />
    </>
  );
};
