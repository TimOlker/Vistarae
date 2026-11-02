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

import React, { useState, useEffect, useMemo } from "react";
import { Modal } from "../common/Modal";
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  HelpCircle,
  RotateCcw,
} from "lucide-react";

export interface ColumnMappingModalProps {
  isOpen: boolean;
  onClose: () => void;
  file: File | null;
  foundHeaders?: string[];
  missingHeaders?: string[];
  onApplyMapping: (mappedFile: File, columnMapping: Record<string, string>) => void;
  isUploading?: boolean;
}

export interface TargetFieldOption {
  key: string;
  label: string;
  required?: boolean;
  description: string;
}

export const VISTARAE_TARGET_FIELDS: TargetFieldOption[] = [
  { key: "poi_name", label: "POI Name (Required)", required: true, description: "Primary name of the travel place, site, or attraction" },
  { key: "street_address", label: "Street Address", description: "Street number and name" },
  { key: "city", label: "City / Town", description: "Municipality or locality" },
  { key: "state_province", label: "State / Province", description: "State, province, or administrative region" },
  { key: "postal_code", label: "Postal / Zip Code", description: "Postal or ZIP code" },
  { key: "country", label: "Country", description: "Country name or ISO code" },
  { key: "latitude", label: "Latitude", description: "Geographic latitude coordinate (-90 to 90)" },
  { key: "longitude", label: "Longitude", description: "Geographic longitude coordinate (-180 to 180)" },
  { key: "dates_visited", label: "Dates Visited", description: "Dates or date ranges when visited" },
  { key: "photo_directory", label: "Photo Directory", description: "Path or URL reference to POI photo" },
  { key: "tags", label: "Tags / Categories", description: "Comma-separated keywords or classifications" },
  { key: "description", label: "Description / Notes", description: "General details, notes, or overview" },
  { key: "reason_to_visit", label: "Reason to Visit", description: "Personal motivation or travel dream context" },
  { key: "confidence_score", label: "Confidence Score", description: "Geocoding confidence or scraper accuracy (0-1)" },
];

/**
 * Robust CSV line splitter that preserves quoted commas.
 */
export function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"' || char === "'") {
      if (inQuotes && line[i + 1] === char) {
        current += char;
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === "," && !inQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

/**
 * Intelligent field matcher for common column name synonyms.
 */
export function suggestFieldMapping(header: string): string {
  const clean = header.toLowerCase().replace(/[^a-z0-9]/g, "");

  if (["name", "poiname", "pointofinterest", "placename", "title", "wonder", "wonders", "attraction", "attractions", "site", "monument", "landmark", "destination", "spot"].includes(clean)) {
    return "poi_name";
  }
  if (clean.includes("wonder") || clean.includes("attraction") || clean.includes("monument") || clean.includes("landmark")) {
    return "poi_name";
  }
  if (["street", "streetaddress", "address", "addr", "location"].includes(clean)) {
    return "street_address";
  }
  if (["city", "town", "locality", "municipality"].includes(clean)) {
    return "city";
  }
  if (["state", "province", "region", "stateprovince"].includes(clean)) {
    return "state_province";
  }
  if (["zip", "zipcode", "postal", "postalcode", "postcode"].includes(clean)) {
    return "postal_code";
  }
  if (["country", "nation"].includes(clean)) {
    return "country";
  }
  if (["lat", "latitude", "y"].includes(clean)) {
    return "latitude";
  }
  if (["lon", "long", "longitude", "lng", "x"].includes(clean)) {
    return "longitude";
  }
  if (["date", "dates", "visited", "datesvisited", "visitdate"].includes(clean)) {
    return "dates_visited";
  }
  if (["photo", "photos", "image", "images", "photodir", "photodirectory", "photopath"].includes(clean)) {
    return "photo_directory";
  }
  if (["tag", "tags", "category", "categories", "type", "types"].includes(clean)) {
    return "tags";
  }
  if (["desc", "description", "notes", "note", "comment", "details", "summary", "overview"].includes(clean)) {
    return "description";
  }
  if (["reason", "reasontovisit", "why"].includes(clean)) {
    return "reason_to_visit";
  }
  if (["confidence", "score", "confidencescore", "confidencepercent"].includes(clean)) {
    return "confidence_score";
  }

  return "";
}

export async function readFileText(file: File): Promise<string> {
  if (typeof file.text === "function") {
    try {
      const res = await file.text();
      if (typeof res === "string" && res.length > 0) return res;
    } catch {
      // fallback to FileReader
    }
  }
  if (typeof FileReader !== "undefined") {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve((reader.result as string) || "");
      reader.onerror = () => resolve("");
      reader.readAsText(file);
    });
  }
  return "";
}

export const ColumnMappingModal: React.FC<ColumnMappingModalProps> = ({
  isOpen,
  onClose,
  file,
  foundHeaders = [],
  missingHeaders = ["name"],
  onApplyMapping,
  isUploading = false,
}) => {
  const [headers, setHeaders] = useState<string[]>([]);
  const [sampleValues, setSampleValues] = useState<Record<string, string>>({});
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [fullFileText, setFullFileText] = useState<string>("");

  useEffect(() => {
    if (!isOpen || !file) {
      return;
    }

    const inspectFile = async () => {
      try {
        const text = await readFileText(file);
        setFullFileText(text);

        const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
        let discoveredHeaders: string[] = [];
        let previewRow: string[] = [];

        if (lines.length > 0) {
          discoveredHeaders = parseCSVLine(lines[0]);
        }
        if (lines.length > 1) {
          previewRow = parseCSVLine(lines[1]);
        }

        // If file parsing yielded empty, fallback to foundHeaders prop
        if (discoveredHeaders.length === 0 && foundHeaders.length > 0) {
          discoveredHeaders = foundHeaders;
        }

        setHeaders(discoveredHeaders);

        const samples: Record<string, string> = {};
        const initialMapping: Record<string, string> = {};

        discoveredHeaders.forEach((col, idx) => {
          samples[col] = previewRow[idx] || "";
          initialMapping[col] = suggestFieldMapping(col);
        });

        setSampleValues(samples);
        setMapping(initialMapping);
      } catch {
        // Fallback to foundHeaders
        if (foundHeaders.length > 0) {
          setHeaders(foundHeaders);
          const initialMapping: Record<string, string> = {};
          foundHeaders.forEach((col) => {
            initialMapping[col] = suggestFieldMapping(col);
          });
          setMapping(initialMapping);
        }
      }
    };

    inspectFile();
  }, [isOpen, file, foundHeaders]);

  const hasPoiNameMapped = useMemo(() => {
    return Object.values(mapping).some((target) => target === "poi_name");
  }, [mapping]);

  const mappedFieldCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    Object.values(mapping).forEach((target) => {
      if (target) {
        counts[target] = (counts[target] || 0) + 1;
      }
    });
    return counts;
  }, [mapping]);

  const handleSelectField = (csvCol: string, targetField: string) => {
    setMapping((prev) => ({
      ...prev,
      [csvCol]: targetField,
    }));
  };

  const handleResetToAuto = () => {
    const fresh: Record<string, string> = {};
    headers.forEach((col) => {
      fresh[col] = suggestFieldMapping(col);
    });
    setMapping(fresh);
  };

  const handleApply = () => {
    if (!hasPoiNameMapped || !file) {
      return;
    }

    // Reconstruct CSV with mapped headers on row 0
    let mappedFile = file;
    if (fullFileText) {
      const lines = fullFileText.split(/\r?\n/);
      if (lines.length > 0) {
        const originalCols = parseCSVLine(lines[0]);
        const newCols = originalCols.map((col) => {
          const mapped = mapping[col];
          return mapped ? mapped : col;
        });

        const newHeaderLine = newCols
          .map((col) => (col.includes(",") ? `"${col}"` : col))
          .join(",");

        const rewrittenContent = [newHeaderLine, ...lines.slice(1)].join("\n");
        mappedFile = new File([rewrittenContent], file.name, {
          type: file.type || "text/csv",
          lastModified: Date.now(),
        });
      }
    }

    onApplyMapping(mappedFile, mapping);
  };

  if (!isOpen) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Map Travel Point Columns"
      maxWidth="720px"
    >
      <div
        data-testid="column-mapping-modal"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          textAlign: "left",
        }}
      >
        {/* Banner Explaining Reason */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "10px",
            padding: "12px 14px",
            borderRadius: "8px",
            backgroundColor: "#fef3c7",
            border: "1px solid #fde68a",
            color: "#92400e",
            fontSize: "13px",
            lineHeight: "1.4",
          }}
        >
          <AlertCircle size={18} style={{ flexShrink: 0, marginTop: "2px", color: "#d97706" }} />
          <div>
            <div style={{ fontWeight: 700, marginBottom: "2px" }}>
              Unmapped Columns Detected
            </div>
            <div>
              Your file <span style={{ fontWeight: 600 }}>{file?.name || "CSV"}</span> is missing the standard{" "}
              <code style={{ background: "#fef9c3", padding: "1px 5px", borderRadius: "4px" }}>
                {missingHeaders.join(", ") || "name"}
              </code>{" "}
              column. Map your file's columns to Vistarae fields below to continue importing.
            </div>
          </div>
        </div>

        {/* Validation Status Pill */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            borderRadius: "6px",
            backgroundColor: hasPoiNameMapped ? "#f0fdf4" : "#fef2f2",
            border: `1px solid ${hasPoiNameMapped ? "#bbf7d0" : "#fecaca"}`,
            color: hasPoiNameMapped ? "#166534" : "#991b1b",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            {hasPoiNameMapped ? (
              <>
                <CheckCircle2 size={16} color="#16a34a" />
                <span>Ready: "POI Name" is assigned.</span>
              </>
            ) : (
              <>
                <AlertCircle size={16} color="#dc2626" />
                <span>Action Required: Please assign at least one column to "POI Name (Required)".</span>
              </>
            )}
          </div>
          <button
            type="button"
            onClick={handleResetToAuto}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              background: "transparent",
              border: "none",
              color: "#475569",
              cursor: "pointer",
              fontSize: "11px",
              fontWeight: 600,
              textDecoration: "underline",
            }}
          >
            <RotateCcw size={12} />
            Auto-Detect
          </button>
        </div>

        {/* Column Mapping Table */}
        <div
          style={{
            maxHeight: "360px",
            overflowY: "auto",
            border: "1px solid var(--border-color, #e2e8f0)",
            borderRadius: "8px",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "12px",
            }}
          >
            <thead>
              <tr
                style={{
                  backgroundColor: "#f8fafc",
                  borderBottom: "1px solid var(--border-color, #e2e8f0)",
                  textAlign: "left",
                }}
              >
                <th style={{ padding: "10px 12px", fontWeight: 700, width: "32%" }}>
                  File Column
                </th>
                <th style={{ padding: "10px 12px", fontWeight: 700, width: "33%" }}>
                  Sample Value (Row 1)
                </th>
                <th style={{ padding: "10px 12px", fontWeight: 700, width: "35%" }}>
                  Maps To Vistarae Field
                </th>
              </tr>
            </thead>
            <tbody>
              {headers.length === 0 ? (
                <tr>
                  <td colSpan={3} style={{ padding: "16px", textAlign: "center", color: "#64748b" }}>
                    No headers detected in file.
                  </td>
                </tr>
              ) : (
                headers.map((col, idx) => {
                  const currentMapped = mapping[col] || "";
                  const isPoiName = currentMapped === "poi_name";
                  const isDuplicate = currentMapped && (mappedFieldCounts[currentMapped] || 0) > 1;

                  return (
                    <tr
                      key={`${col}-${idx}`}
                      data-testid="column-mapping-row"
                      style={{
                        borderBottom: "1px solid #f1f5f9",
                        backgroundColor: isPoiName ? "#f8fafc" : "white",
                      }}
                    >
                      <td style={{ padding: "8px 12px", fontWeight: 600, color: "#1e293b" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <FileSpreadsheet size={14} color="#64748b" />
                          <span>{col}</span>
                        </div>
                      </td>
                      <td
                        style={{
                          padding: "8px 12px",
                          color: "#64748b",
                          maxWidth: "180px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={sampleValues[col] || "(empty)"}
                      >
                        {sampleValues[col] ? (
                          <span>{sampleValues[col]}</span>
                        ) : (
                          <span style={{ fontStyle: "italic", color: "#94a3b8" }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: "8px 12px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <select
                            data-testid={`select-mapping-${col}`}
                            value={currentMapped}
                            onChange={(e) => handleSelectField(col, e.target.value)}
                            style={{
                              width: "100%",
                              padding: "6px 8px",
                              borderRadius: "6px",
                              border: isPoiName
                                ? "1px solid #16a34a"
                                : isDuplicate
                                ? "1px solid #f59e0b"
                                : "1px solid #cbd5e1",
                              backgroundColor: isPoiName ? "#f0fdf4" : "white",
                              fontSize: "12px",
                              fontWeight: isPoiName ? 600 : 400,
                              color: "#0f172a",
                            }}
                          >
                            <option value="">-- Do Not Import / Skip --</option>
                            <optgroup label="Required Field">
                              <option value="poi_name">POI Name (Required)</option>
                            </optgroup>
                            <optgroup label="Standard Fields">
                              {VISTARAE_TARGET_FIELDS.filter((f) => f.key !== "poi_name").map((field) => (
                                <option key={field.key} value={field.key}>
                                  {field.label}
                                </option>
                              ))}
                            </optgroup>
                          </select>
                          {isDuplicate && (
                            <span style={{ fontSize: "10px", color: "#d97706" }}>
                              Warning: "{currentMapped}" is mapped more than once.
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer Actions */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: "4px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
            <HelpCircle size={13} />
            <span>Unmapped columns will be ignored during import.</span>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              style={{
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 6px)",
                background: "#f1f5f9",
                color: "#475569",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              data-testid="apply-column-mapping-btn"
              onClick={handleApply}
              disabled={!hasPoiNameMapped || isUploading}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 6px)",
                background: hasPoiNameMapped ? "var(--accent, #2563eb)" : "#94a3b8",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor: hasPoiNameMapped && !isUploading ? "pointer" : "not-allowed",
              }}
            >
              <span>Apply Mapping & Import</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
