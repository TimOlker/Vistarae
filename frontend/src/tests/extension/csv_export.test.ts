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

import { describe, it, expect } from "vitest";

/**
 * Sanitizes a cell value for RFC 4180 CSV export and formula injection neutralization.
 * Any string starting with =, +, -, @, or tab is prepended with a single quote (').
 *
 * @param {any} val
 * @returns {string} Escaped CSV field
 */
export function sanitizeCsvField(val: any): string {
  if (val === null || val === undefined) return "";
  const str = String(val);

  // Neutralize formula injection characters
  let safeStr = str;
  if (/^[=+\-@\t\r]/.test(safeStr)) {
    safeStr = "'" + safeStr;
  }

  // RFC 4180 quoting if field contains comma, quote, or newline
  if (/[",\n\r]/.test(safeStr)) {
    safeStr = `"${safeStr.replace(/"/g, '""')}"`;
  }

  return safeStr;
}

/**
 * Generates an RFC 4180 compliant CSV string from an array of POI records.
 *
 * @param {Array<Record<string, any>>} records
 * @returns {string} CSV content
 */
export function generatePoiCsv(records: Array<Record<string, any>>): string {
  const headers = [
    "Name",
    "Category",
    "Address",
    "City",
    "State",
    "Country",
    "Latitude",
    "Longitude",
    "Rating",
    "Source URL",
    "Tags",
  ];

  const lines = [headers.map(sanitizeCsvField).join(",")];

  for (const poi of records) {
    const row = [
      poi.name,
      poi.category,
      poi.address,
      poi.city,
      poi.state,
      poi.country,
      poi.latitude,
      poi.longitude,
      poi.rating,
      poi.source_url,
      Array.isArray(poi.tags) ? poi.tags.join("; ") : poi.tags,
    ];
    lines.push(row.map(sanitizeCsvField).join(","));
  }

  return lines.join("\r\n");
}

describe("RFC 4180 CSV Export & Formula Injection Neutralization", () => {
  it("neutralizes formula injection characters (=, +, -, @) by prepending a single quote", () => {
    expect(sanitizeCsvField("=cmd|/C calc.exe!A0")).toBe(
      "'=cmd|/C calc.exe!A0",
    );
    expect(sanitizeCsvField("+SUM(A1:A10)")).toBe("'+SUM(A1:A10)");
    expect(sanitizeCsvField("-10% discount")).toBe("'-10% discount");
    expect(sanitizeCsvField("@SUM(B1:B5)")).toBe("'@SUM(B1:B5)");
  });

  it("escapes quotes and wraps fields containing commas in double quotes per RFC 4180", () => {
    expect(sanitizeCsvField("Yosemite Valley, CA")).toBe(
      '"Yosemite Valley, CA"',
    );
    expect(sanitizeCsvField('The "Great" Canyon')).toBe(
      '"The ""Great"" Canyon"',
    );
    expect(sanitizeCsvField("Line 1\nLine 2")).toBe('"Line 1\nLine 2"');
  });

  it("generates compliant CSV with sanitized rows for travel POIs", () => {
    const testPois = [
      {
        name: "=Dangerous Formula POI",
        category: "viewpoint",
        address: "100 Scenic Way, Overlook",
        city: "Yosemite",
        state: "CA",
        country: "US",
        latitude: 37.74,
        longitude: -119.59,
        rating: 5,
        source_url: "https://example.com/poi",
        tags: ["scenic", "overlook"],
      },
      {
        name: "Half Dome, Cable Route",
        category: "trail",
        address: "Curry Village",
        city: "Yosemite",
        state: "CA",
        country: "US",
        latitude: 37.745,
        longitude: -119.533,
        rating: 5,
        source_url: "https://example.com/half-dome",
        tags: ["permit-required"],
      },
    ];

    const csv = generatePoiCsv(testPois);
    const lines = csv.split("\r\n");

    expect(lines.length).toBe(3);
    expect(lines[0]).toBe(
      "Name,Category,Address,City,State,Country,Latitude,Longitude,Rating,Source URL,Tags",
    );
    // First POI formula must be neutralized
    expect(lines[1]).toContain("'=Dangerous Formula POI");
    // Second POI name with comma must be wrapped in quotes
    expect(lines[2]).toContain('"Half Dome, Cable Route"');
  });
});
