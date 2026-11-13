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
 * Authoritative canonical schema registry and serialization definitions for 017-export.
 * Synchronized with packages/core/vistarae_core/schemas/export_schema.py.
 */

export const UTF8_BOM = "\ufeff";
export const FORMULA_PREFIXES = ["=", "+", "-", "@", "\t", "\r"] as const;

export type ExportFieldType =
  | "string"
  | "number"
  | "boolean"
  | "string_list"
  | "json_pairs"
  | "uuid";

export interface ExportFieldDefinition {
  attribute_key: string;
  header_name: string;
  field_type: ExportFieldType;
  aliases: string[];
  is_formula_sanitized?: boolean;
  default_value?: any;
}

/**
 * Neutralizes spreadsheet formula injection by prepending a single quote.
 */
export function sanitizeFormulaPrefix(val: string): string {
  if (!val) return "";
  for (const prefix of FORMULA_PREFIXES) {
    if (val.startsWith(prefix)) {
      return `'${val}`;
    }
  }
  return val;
}

/**
 * Strips formula-neutralizing leading single quote if followed by a formula prefix.
 */
export function desanitizeFormulaPrefix(val: string): string {
  if (!val) return "";
  if (val.startsWith("'") && val.length > 1) {
    const rest = val.slice(1);
    for (const prefix of FORMULA_PREFIXES) {
      if (rest.startsWith(prefix)) {
        return rest;
      }
    }
  }
  return val;
}

/**
 * Serializes a string list as semicolon-separated values.
 */
export function serializeStringList(items?: string[] | null): string {
  if (!items || !items.length) return "";
  return items
    .map((item) => String(item).trim())
    .filter(Boolean)
    .join("; ");
}

/**
 * Deserializes a string into a list of strings, supporting JSON arrays and semicolon/comma strings.
 */
export function deserializeStringList(val?: string | null): string[] {
  if (!val) return [];
  const trimmed = val.trim();
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item).trim()).filter(Boolean);
      }
    } catch {
      // fallback to delimiter split
    }
  }
  const delimiter = trimmed.includes(";") ? ";" : ",";
  return trimmed
    .split(delimiter)
    .map((item) => item.trim())
    .filter(Boolean);
}

/**
 * Serializes structured object pairs to a JSON string.
 */
export function serializeJsonPairs(items?: any[] | null): string {
  if (!items || !items.length) return "";
  return JSON.stringify(items);
}

/**
 * Deserializes a cell containing structured object pairs.
 */
export function deserializeJsonPairs(
  val?: string | null,
): Array<{ name?: string; url?: string; [k: string]: any }> {
  if (!val) return [];
  const trimmed = val.trim();
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => {
          if (typeof item === "object" && item !== null) return item;
          const s = String(item).trim();
          return { name: s, url: s };
        });
      }
    } catch {
      // fallback
    }
  }
  const delimiter = trimmed.includes(";") ? ";" : ",";
  return trimmed
    .split(delimiter)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((url) => ({ name: url, url }));
}

/**
 * Escapes a cell according to RFC 4180 rules.
 */
export function formatCsvCell(val: string): string {
  if (!val) return "";
  if (
    val.includes(",") ||
    val.includes('"') ||
    val.includes("\n") ||
    val.includes("\r")
  ) {
    return `"${val.replace(/"/g, '""')}"`;
  }
  return val;
}

export const CANONICAL_EXPORT_FIELDS: ExportFieldDefinition[] = [
  {
    attribute_key: "candidate_id",
    header_name: "Candidate ID",
    field_type: "uuid",
    aliases: ["candidate_id", "candidate id", "id"],
  },
  {
    attribute_key: "row_index",
    header_name: "Row Index",
    field_type: "number",
    aliases: ["row_index", "row index", "line_number"],
    default_value: 0,
  },
  {
    attribute_key: "poi_name",
    header_name: "POI Name",
    field_type: "string",
    aliases: ["poi_name", "poi name", "name", "title", "attraction"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "street_address",
    header_name: "Street Address",
    field_type: "string",
    aliases: ["street_address", "street address", "address", "street"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "city",
    header_name: "City / Town",
    field_type: "string",
    aliases: ["city", "town_city", "town/city", "town", "municipality"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "locality",
    header_name: "Locality",
    field_type: "string",
    aliases: ["locality", "neighborhood", "suburb"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "admin_level_2",
    header_name: "County / District (Admin Level 2)",
    field_type: "string",
    aliases: ["admin_level_2", "admin level 2", "county", "district"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "admin_level_1",
    header_name: "State / Province (Admin Level 1)",
    field_type: "string",
    aliases: ["admin_level_1", "admin level 1", "state", "province", "region"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "state_province",
    header_name: "State / Province",
    field_type: "string",
    aliases: ["state_province", "state/province"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "postal_code",
    header_name: "Postal Code / Zip",
    field_type: "string",
    aliases: [
      "postal_code",
      "postal code",
      "zip_code",
      "zip code",
      "zip",
      "postcode",
    ],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "country",
    header_name: "Country",
    field_type: "string",
    aliases: ["country", "nation"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "country_code",
    header_name: "Country Code",
    field_type: "string",
    aliases: ["country_code", "country code", "iso_country"],
    is_formula_sanitized: false,
  },
  {
    attribute_key: "latitude",
    header_name: "Latitude",
    field_type: "number",
    aliases: ["latitude", "lat"],
  },
  {
    attribute_key: "longitude",
    header_name: "Longitude",
    field_type: "number",
    aliases: ["longitude", "lon", "lng"],
  },
  {
    attribute_key: "recommended_disposition",
    header_name: "Recommended Disposition",
    field_type: "string",
    aliases: ["recommended_disposition", "recommended disposition"],
    default_value: "accept",
  },
  {
    attribute_key: "user_disposition",
    header_name: "User Disposition",
    field_type: "string",
    aliases: ["user_disposition", "user disposition", "disposition"],
  },
  {
    attribute_key: "confidence_score",
    header_name: "Confidence Score",
    field_type: "number",
    aliases: [
      "confidence_score",
      "confidence score",
      "location_confidence_percent",
      "confidence",
    ],
    default_value: 0,
  },
  {
    attribute_key: "disposition_justification",
    header_name: "Disposition Justification",
    field_type: "string",
    aliases: [
      "disposition_justification",
      "disposition justification",
      "rejection_reason",
      "rationale",
    ],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "description",
    header_name: "Description",
    field_type: "string",
    aliases: ["description", "ai_description", "overview"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "reason_to_visit",
    header_name: "Reason to Visit",
    field_type: "string",
    aliases: ["reason_to_visit", "reason to visit", "why_visit"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "hero_image_url",
    header_name: "Hero Image URL",
    field_type: "string",
    aliases: [
      "hero_image_url",
      "hero image url",
      "hero photo url",
      "image_url",
    ],
  },
  {
    attribute_key: "official_url",
    header_name: "Official URL",
    field_type: "string",
    aliases: [
      "official_url",
      "official url",
      "official website",
      "official_website",
    ],
  },
  {
    attribute_key: "wiki_url",
    header_name: "Wikipedia URL",
    field_type: "string",
    aliases: ["wiki_url", "wikipedia url", "wikipedia_url", "wiki url"],
  },
  {
    attribute_key: "related_websites",
    header_name: "Related Websites",
    field_type: "json_pairs",
    aliases: ["related_websites", "related websites", "websites"],
  },
  {
    attribute_key: "no_websites",
    header_name: "No Websites Flag",
    field_type: "boolean",
    aliases: ["no_websites", "no websites", "no_websites_flag"],
    default_value: false,
  },
  {
    attribute_key: "tags",
    header_name: "Tags",
    field_type: "string_list",
    aliases: ["tags", "categories"],
  },
  {
    attribute_key: "photo_directory",
    header_name: "Photo Directory",
    field_type: "string",
    aliases: ["photo_directory", "photo directory"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "photo_directories",
    header_name: "Photo Directories",
    field_type: "string_list",
    aliases: ["photo_directories", "photo directories"],
  },
  {
    attribute_key: "dates_visited",
    header_name: "Dates Visited",
    field_type: "string_list",
    aliases: ["dates_visited", "dates visited", "visited_dates"],
  },
  {
    attribute_key: "recommended_duration_hours",
    header_name: "Recommended Duration Hours",
    field_type: "number",
    aliases: [
      "recommended_duration_hours",
      "estimated visit hours",
      "estimated_visit_hours",
    ],
  },
  {
    attribute_key: "recommended_visit_days",
    header_name: "Recommended Visit Days",
    field_type: "number",
    aliases: ["recommended_visit_days", "itinerary days", "itinerary_days"],
  },
  {
    attribute_key: "estimated_visit_time_notes",
    header_name: "Estimated Visit Time Notes",
    field_type: "string",
    aliases: ["estimated_visit_time_notes", "visit_time_notes"],
    is_formula_sanitized: true,
  },
  {
    attribute_key: "parent_candidate_id",
    header_name: "Parent Candidate ID",
    field_type: "uuid",
    aliases: ["parent_candidate_id", "parent candidate id"],
  },
  {
    attribute_key: "parent_poi_id",
    header_name: "Parent POI ID",
    field_type: "uuid",
    aliases: ["parent_poi_id", "parent poi id"],
  },
  {
    attribute_key: "matched_existing_poi_id",
    header_name: "Matched Existing POI ID",
    field_type: "uuid",
    aliases: ["matched_existing_poi_id", "matched existing poi id"],
  },
  {
    attribute_key: "merge_target_id",
    header_name: "Merge Target ID",
    field_type: "uuid",
    aliases: ["merge_target_id", "merge target id"],
  },
  {
    attribute_key: "is_user_overridden",
    header_name: "Is User Overridden",
    field_type: "boolean",
    aliases: ["is_user_overridden", "is user overridden", "user_overridden"],
    default_value: false,
  },
];
