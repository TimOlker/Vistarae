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
import {
  CANONICAL_EXPORT_FIELDS,
  desanitizeFormulaPrefix,
  deserializeJsonPairs,
  deserializeStringList,
  formatCsvCell,
  sanitizeFormulaPrefix,
  serializeJsonPairs,
  serializeStringList,
} from "../../types/export-schema";

describe("Frontend Export Schema & Utilities", () => {
  it("defines exactly 37 canonical export fields", () => {
    expect(CANONICAL_EXPORT_FIELDS.length).toBe(37);
    const keys = new Set(CANONICAL_EXPORT_FIELDS.map((f) => f.attribute_key));
    expect(keys.has("poi_name")).toBe(true);
    expect(keys.has("locality")).toBe(true);
    expect(keys.has("admin_level_2")).toBe(true);
    expect(keys.has("related_websites")).toBe(true);
    expect(keys.has("tags")).toBe(true);
  });

  it("sanitizes formula prefix triggers with leading quote", () => {
    expect(sanitizeFormulaPrefix("=SUM(1+1)")).toBe("'=SUM(1+1)");
    expect(sanitizeFormulaPrefix("+123")).toBe("'+123");
    expect(sanitizeFormulaPrefix("-50")).toBe("'-50");
    expect(sanitizeFormulaPrefix("@Admin")).toBe("'@Admin");
    expect(sanitizeFormulaPrefix("Normal Text")).toBe("Normal Text");
  });

  it("desanitizes leading quote when followed by formula prefix", () => {
    expect(desanitizeFormulaPrefix("'=SUM(1+1)")).toBe("=SUM(1+1)");
    expect(desanitizeFormulaPrefix("'+123")).toBe("+123");
    expect(desanitizeFormulaPrefix("'Normal Text")).toBe("'Normal Text");
  });

  it("serializes and deserializes string lists with dual-mode support", () => {
    const list = ["Volcano", "Scenic", "National Park"];
    const serialized = serializeStringList(list);
    expect(serialized).toBe("Volcano; Scenic; National Park");

    expect(deserializeStringList(serialized)).toEqual(list);
    expect(
      deserializeStringList('["Volcano", "Scenic", "National Park"]'),
    ).toEqual(list);
    expect(deserializeStringList(" Volcano ; Scenic ; National Park ")).toEqual(
      list,
    );
  });

  it("serializes and deserializes JSON pairs with fallback", () => {
    const pairs = [
      { name: "NPS Site", url: "https://nps.gov" },
      { name: "Guide", url: "https://example.com" },
    ];
    const serialized = serializeJsonPairs(pairs);
    expect(deserializeJsonPairs(serialized)).toEqual(pairs);

    const fallback = deserializeJsonPairs(
      "https://nps.gov; https://example.com",
    );
    expect(fallback.length).toBe(2);
    expect(fallback[0].url).toBe("https://nps.gov");
  });

  it("formats CSV cells complying with RFC 4180", () => {
    expect(formatCsvCell("clean")).toBe("clean");
    expect(formatCsvCell("has,comma")).toBe('"has,comma"');
    expect(formatCsvCell('has"quote')).toBe('"has""quote"');
    expect(formatCsvCell("has\nnewline")).toBe('"has\nnewline"');
  });
});
