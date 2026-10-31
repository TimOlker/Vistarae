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

import { apiFetch } from "./api";

export interface ExclusionZoneItem {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  radius_km: number;
  created_at: string;
  updated_at: string;
}

export interface ExclusionCheckResult {
  is_excluded: boolean;
  matched_zones: ExclusionZoneItem[];
  matched_zone_names: string[];
}

/**
 * Calculates great-circle distance between two coordinates in kilometers using Haversine formula.
 */
export function haversineDistanceKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const R = 6371; // Earth's radius in km
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Client-side evaluation of coordinates against active exclusion zones.
 */
export function checkCoordinatesAgainstExclusionZones(
  lat: number,
  lon: number,
  zones: ExclusionZoneItem[],
): { isExcluded: boolean; matchedZones: ExclusionZoneItem[] } {
  const matched = zones.filter((z) => {
    const dist = haversineDistanceKm(lat, lon, z.latitude, z.longitude);
    return dist <= z.radius_km;
  });
  return {
    isExcluded: matched.length > 0,
    matchedZones: matched,
  };
}

export const exclusionZoneService = {
  async getExclusionZones(): Promise<ExclusionZoneItem[]> {
    const res = await apiFetch<{ items: ExclusionZoneItem[] }>("/api/user/exclusion-zones");
    return res.items || [];
  },

  async createExclusionZone(data: {
    name: string;
    latitude: number;
    longitude: number;
    radius_km: number;
  }): Promise<ExclusionZoneItem> {
    return apiFetch<ExclusionZoneItem>("/api/user/exclusion-zones", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateExclusionZone(
    zoneId: string,
    data: Partial<{
      name: string;
      latitude: number;
      longitude: number;
      radius_km: number;
    }>,
  ): Promise<ExclusionZoneItem> {
    return apiFetch<ExclusionZoneItem>(`/api/user/exclusion-zones/${zoneId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async deleteExclusionZone(zoneId: string): Promise<void> {
    await apiFetch(`/api/user/exclusion-zones/${zoneId}`, {
      method: "DELETE",
    });
  },

  async checkPointExclusion(latitude: number, longitude: number): Promise<ExclusionCheckResult> {
    return apiFetch<ExclusionCheckResult>("/api/user/exclusion-zones/check", {
      method: "POST",
      body: JSON.stringify({ latitude, longitude }),
    });
  },
};

