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

import { describe, expect, it } from "vitest";
import { UTF8_BOM } from "../../types/export-schema";
import {
  exportWorkbenchCandidatesToCsv,
  serializeCandidateToRow,
} from "../../utils/csvExport";
import {
  getSampleWorkbenchCandidates,
  SAMPLE_CANDIDATE_1_ID,
  SAMPLE_PARENT_ID,
} from "../fixtures/exportFixtures";

describe("exportWorkbenchCandidatesToCsv", () => {
  it("serializes all 37 canonical headers and fields", () => {
    const candidates = getSampleWorkbenchCandidates();
    const result = exportWorkbenchCandidatesToCsv(candidates, {
      triggerDownload: false,
    });

    expect(result.exportedCount).toBe(2);
    expect(result.csvContent.startsWith(UTF8_BOM)).toBe(true);

    const lines = result.csvContent.slice(UTF8_BOM.length).split("\r\n");
    expect(lines.length).toBe(3); // Header + 2 rows

    const headerCols = lines[0].split(",");
    expect(headerCols.length).toBe(37);
    expect(headerCols[0]).toBe("Candidate ID");
    expect(headerCols[2]).toBe("POI Name");
  });

  it("neutralizes spreadsheet formula prefixes in text fields", () => {
    const candidates = getSampleWorkbenchCandidates();
    const result = exportWorkbenchCandidatesToCsv(candidates, {
      triggerDownload: false,
    });
    const lines = result.csvContent.slice(UTF8_BOM.length).split("\r\n");

    // Candidate 2 has "=Grand Prismatic Spring" -> should be "'=Grand Prismatic Spring"
    const row2 = lines[2];
    expect(row2).toContain("'=Grand Prismatic Spring");
    expect(row2).toContain("'+Sublocation nested");
    expect(row2).toContain("'@Largest hot spring");
    expect(row2).toContain("'-Stunning aerial");
  });

  it("flushes active editor candidate before export", () => {
    const candidates = getSampleWorkbenchCandidates();
    const activeEditor = {
      id: SAMPLE_PARENT_ID,
      description: "NEW FLUSHED DESCRIPTION FROM ACTIVE FORM",
    };

    const result = exportWorkbenchCandidatesToCsv(candidates, {
      activeEditorCandidate: activeEditor,
      triggerDownload: false,
    });

    expect(result.csvContent).toContain(
      "NEW FLUSHED DESCRIPTION FROM ACTIVE FORM",
    );
  });

  it("exports only selected rows when selectedCandidateIds has items", () => {
    const candidates = getSampleWorkbenchCandidates();
    const selectedIds = new Set([SAMPLE_CANDIDATE_1_ID]);

    const result = exportWorkbenchCandidatesToCsv(candidates, {
      selectedCandidateIds: selectedIds,
      triggerDownload: false,
    });

    expect(result.exportedCount).toBe(1);
    expect(result.csvContent).toContain("Grand Prismatic Spring");
    expect(result.csvContent).not.toContain("2 Officers Row");

    const lines = result.csvContent.slice(UTF8_BOM.length).split("\r\n");
    expect(lines.length).toBe(2); // Header + 1 row
    expect(lines[1].startsWith(SAMPLE_CANDIDATE_1_ID)).toBe(true);
  });

  it("exports all candidates when selectedCandidateIds is empty or omitted", () => {
    const candidates = getSampleWorkbenchCandidates();
    const result = exportWorkbenchCandidatesToCsv(candidates, {
      selectedCandidateIds: new Set(),
      triggerDownload: false,
    });

    expect(result.exportedCount).toBe(2);
  });
});
