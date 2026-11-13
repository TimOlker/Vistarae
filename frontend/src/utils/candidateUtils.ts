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

import type { CandidateItem } from "../services/ingestApi";

/**
 * Returns a human-friendly city or prefecture name for a candidate POI in the
 * staging workbench, handling special geographic edge cases such as Hong Kong
 * and Chinese municipalities / prefectures.
 */
export function getDisplayCandidateCity(cand: CandidateItem): string {
  const prov = (cand.state_province || cand.admin_level_1 || "").toLowerCase();
  const cName = (cand.country || "").toLowerCase();
  const poiName = (cand.poi_name || "").toLowerCase();
  const cityName = (cand.city || "").toLowerCase();

  const isHongKong =
    cName === "hong kong" ||
    cand.country_code === "HK" ||
    ["hong kong", "kowloon", "new territories", "hong kong island"].includes(
      prov,
    ) ||
    poiName.includes("hong kong") ||
    cityName.includes("mong kok") ||
    cityName.includes("tsim sha tsui") ||
    cityName.includes("fife street");

  if (isHongKong) {
    return "Hong Kong";
  }

  if (
    cand.country_code === "CN" ||
    cand.country === "China" ||
    cand.country === "中国"
  ) {
    const isChineseDistrict = (name: string | null | undefined): boolean => {
      if (!name) return false;
      const nl = name.trim().toLowerCase();
      return (
        nl.includes("district") ||
        nl.includes("subdistrict") ||
        nl === "pudong" ||
        nl === "pudong new area" ||
        (/[\u4e00-\u9fff]/.test(name) &&
          (name.includes("区") || name.includes("街道") || name.includes("旗")))
      );
    };

    if (isChineseDistrict(cand.city)) {
      const prov = cand.state_province || cand.admin_level_1 || "";
      if (["Beijing", "Shanghai", "Tianjin", "Chongqing"].includes(prov)) {
        return prov;
      }
      const rawGeo = (cand.raw_geocoding || {}) as Record<string, any>;
      const disp = String(rawGeo.display_name || "");
      if (disp) {
        const parts = disp
          .split(",")
          .map((p) => p.trim())
          .filter(Boolean);
        let a1Idx = -1;
        for (let i = 0; i < parts.length; i++) {
          if (
            prov &&
            (prov.toLowerCase() === parts[i].toLowerCase() ||
              parts[i].toLowerCase().startsWith(prov.toLowerCase()))
          ) {
            a1Idx = i;
            break;
          }
        }
        if (a1Idx > 0) {
          for (let i = a1Idx - 1; i >= 0; i--) {
            const seg = parts[i];
            if (/^\d+$/.test(seg) || isChineseDistrict(seg)) continue;
            return seg.replace(/\s+Prefecture$/, "");
          }
        }
      }
      const pLow = (cand.poi_name || "").toLowerCase();
      if (
        pLow.includes("wild goose") ||
        pLow.includes("terra cotta") ||
        pLow.includes("terracotta")
      )
        return "Xi'an";
      if (
        pLow.includes("jokhang") ||
        pLow.includes("potala") ||
        pLow.includes("sera")
      )
        return "Lhasa";
      if (pLow.includes("longmen")) return "Luoyang";
      if (pLow.includes("leshan")) return "Leshan";
      if (pLow.includes("jade buddha") || pLow.includes("bund"))
        return "Shanghai";
    }
  }
  return cand.city || "-";
}

