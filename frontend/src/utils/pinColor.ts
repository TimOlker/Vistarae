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

import type { POIMapFeature } from "../types/map";
import type { PinColorScheme } from "../types/filter";

/**
 * Computes the marker pin color for a POI based on the active PinColorScheme (REQ-MAIN-020, REQ-MAIN-021).
 */
export function computePoiPinColor(
  poi: POIMapFeature,
  scheme?: PinColorScheme,
): string {
  if (!scheme) return "#2563eb";

  const defaultColor = scheme.default_color || "#2563eb";

  if (scheme.mode === "uniform") {
    return defaultColor;
  }

  if (scheme.mode === "rating") {
    const ratingKey = String(poi.rating ?? 0);
    return scheme.palette?.[ratingKey] || defaultColor;
  }

  if (scheme.mode === "visit_status") {
    const statusKey = poi.visit_state || "not_visited";
    return scheme.palette?.[statusKey] || defaultColor;
  }

  if (scheme.mode === "custom" && scheme.rule_mappings?.length) {
    for (const mapping of scheme.rule_mappings) {
      if (!mapping.field || !mapping.color) continue;

      if (mapping.field === "tag" && poi.tags && Array.isArray(poi.tags)) {
        if (
          poi.tags.some(
            (t) => t.toLowerCase() === String(mapping.value).toLowerCase(),
          )
        ) {
          return mapping.color;
        }
      } else if (mapping.field === "country" && poi.country) {
        if (poi.country.toLowerCase() === String(mapping.value).toLowerCase()) {
          return mapping.color;
        }
      } else if (mapping.field === "city" && poi.city) {
        if (poi.city.toLowerCase() === String(mapping.value).toLowerCase()) {
          return mapping.color;
        }
      } else if (mapping.field === "visit_state" && poi.visit_state) {
        if (poi.visit_state === mapping.value) {
          return mapping.color;
        }
      }
    }
  }

  return defaultColor;
}
