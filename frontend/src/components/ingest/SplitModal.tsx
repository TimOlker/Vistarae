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

import React from "react";
import { Modal } from "../common/Modal";
import { AlertTriangle, Split } from "lucide-react";

interface SplitModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileName: string;
  fileSizeBytes: number;
  rowCount: number;
}

export const SplitModal: React.FC<SplitModalProps> = ({
  isOpen,
  onClose,
  fileName,
  fileSizeBytes,
  rowCount,
}) => {
  const isOverSize = fileSizeBytes > 2 * 1024 * 1024;
  const isOverRows = rowCount > 2000;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="File Limit Exceeded"
      maxWidth="480px"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "12px",
            padding: "12px",
            borderRadius: "8px",
            background: "#fffbeb",
            border: "1px solid #fde68a",
          }}
        >
          <AlertTriangle
            size={24}
            color="#b45309"
            style={{ flexShrink: 0, marginTop: "2px" }}
          />
          <div>
            <h4 style={{ fontSize: "14px", fontWeight: 700, color: "#92400e" }}>
              Dataset exceeds ingestion guardrails
            </h4>
            <p style={{ fontSize: "12px", color: "#b45309", marginTop: "2px" }}>
              To ensure low-latency geospatial clustering and AWS queue
              discipline, files must stay within <strong>2.0 MB</strong> and{" "}
              <strong>2,000 rows</strong>.
            </p>
          </div>
        </div>

        <div
          style={{
            fontSize: "13px",
            lineHeight: 1.5,
            color: "var(--text-secondary)",
          }}
        >
          <p>
            File <strong>{fileName}</strong>:
          </p>
          <ul style={{ paddingLeft: "20px", marginTop: "4px" }}>
            <li style={{ color: isOverSize ? "var(--danger)" : "inherit" }}>
              Size: {(fileSizeBytes / (1024 * 1024)).toFixed(2)} MB{" "}
              {isOverSize ? "(Max 2.0 MB)" : "✓"}
            </li>
            <li style={{ color: isOverRows ? "var(--danger)" : "inherit" }}>
              Rows: {rowCount.toLocaleString()}{" "}
              {isOverRows ? "(Max 2,000 rows)" : "✓"}
            </li>
          </ul>
        </div>

        <div
          style={{
            padding: "12px",
            background: "var(--bg-hover, #f8fafc)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontWeight: 700,
              marginBottom: "6px",
            }}
          >
            <Split size={14} />
            <span>How to partition your CSV:</span>
          </div>
          <ol
            style={{
              paddingLeft: "18px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}
          >
            <li>
              Open the CSV file in Excel, Google Sheets, or your text editor.
            </li>
            <li>
              Split the rows into 2 or more files, retaining the original header
              row in each part.
            </li>
            <li>
              Export each part as an independent CSV file ($\le 2,000$ rows) and
              upload them sequentially.
            </li>
          </ol>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            marginTop: "8px",
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            Got It
          </button>
        </div>
      </div>
    </Modal>
  );
};
