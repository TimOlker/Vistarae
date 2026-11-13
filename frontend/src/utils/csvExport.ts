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

/**
 * Client-side RFC 4180 full-fidelity CSV export serializer for 017-export.
 */

import {
  CANONICAL_EXPORT_FIELDS,
  ExportFieldDefinition,
  formatCsvCell,
  sanitizeFormulaPrefix,
  serializeJsonPairs,
  serializeStringList,
  UTF8_BOM,
} from "../types/export-schema";

export interface ExportWorkbenchOptions {
  jobId?: string;
  selectedCandidateIds?: Set<string>;
  activeEditorCandidate?: any | null;
  triggerDownload?: boolean;
}

export interface ExportWorkbenchResult {
  exportedCount: number;
  filename: string;
  csvContent: string;
}

/**
 * Serializes a single candidate item into an ordered array of CSV cell values.
 */
export function serializeCandidateToRow(cand: any): string[] {
  return CANONICAL_EXPORT_FIELDS.map((fieldDef: ExportFieldDefinition) => {
    let rawVal = cand[fieldDef.attribute_key];

    // Special fallback for candidate_id / id
    if (
      fieldDef.attribute_key === "candidate_id" &&
      (rawVal === undefined || rawVal === null)
    ) {
      rawVal = cand.id;
    }

    if (rawVal === undefined || rawVal === null) {
      rawVal =
        fieldDef.default_value !== undefined ? fieldDef.default_value : "";
    }

    let formattedStr = "";
    if (fieldDef.field_type === "string_list") {
      formattedStr = serializeStringList(
        Array.isArray(rawVal) ? rawVal : [rawVal],
      );
    } else if (fieldDef.field_type === "json_pairs") {
      formattedStr = serializeJsonPairs(Array.isArray(rawVal) ? rawVal : []);
    } else if (fieldDef.field_type === "boolean") {
      formattedStr = rawVal ? "true" : "false";
    } else if (fieldDef.field_type === "number") {
      formattedStr = rawVal !== "" && rawVal !== null ? String(rawVal) : "";
    } else if (fieldDef.field_type === "uuid") {
      formattedStr = rawVal ? String(rawVal) : "";
    } else {
      formattedStr = String(rawVal);
      if (fieldDef.is_formula_sanitized) {
        formattedStr = sanitizeFormulaPrefix(formattedStr);
      }
    }

    return formatCsvCell(formattedStr);
  });
}

/**
 * Serializes workbench candidates into an RFC 4180 CSV string with UTF-8 BOM,
 * honoring candidate selection scope and active detail editor flush.
 */
export function exportWorkbenchCandidatesToCsv(
  candidates: any[],
  options?: ExportWorkbenchOptions,
): ExportWorkbenchResult {
  const triggerDownload = options?.triggerDownload ?? true;

  // 1. Flush active editor inputs into working candidate set
  let workingCandidates = [...candidates];
  if (options?.activeEditorCandidate) {
    const editorId =
      options.activeEditorCandidate.candidate_id ||
      options.activeEditorCandidate.id;
    workingCandidates = workingCandidates.map((c) => {
      const cId = c.candidate_id || c.id;
      if (cId && editorId && cId === editorId) {
        return { ...c, ...options.activeEditorCandidate };
      }
      return c;
    });
  }

  // 2. Resolve export scope (selected rows if any checked, otherwise all)
  let targetCandidates = workingCandidates;
  if (options?.selectedCandidateIds && options.selectedCandidateIds.size > 0) {
    targetCandidates = workingCandidates.filter((c) => {
      const cId = c.candidate_id || c.id;
      return cId && options.selectedCandidateIds!.has(cId);
    });
  }

  // 3. Assemble CSV header and rows
  const headers = CANONICAL_EXPORT_FIELDS.map((f) =>
    formatCsvCell(f.header_name),
  );
  const rows = targetCandidates.map((c) => serializeCandidateToRow(c));

  const csvBody = [headers.join(","), ...rows.map((r) => r.join(","))].join(
    "\r\n",
  );
  const fullContent = `${UTF8_BOM}${csvBody}`;

  const nowStr = new Date().toISOString().split("T")[0];
  const filename = `vistarae_staging_${
    options?.jobId || "export"
  }_${nowStr}.csv`;

  // 4. Trigger browser download if requested
  if (triggerDownload && typeof document !== "undefined") {
    const blob = new Blob([fullContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.style.display = "none";
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }, 1000);
  }

  return {
    exportedCount: targetCandidates.length,
    filename,
    csvContent: fullContent,
  };
}
