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
 * Client-side geocoding service supporting browser forward search
 * and backend cached reverse geocoding via PostGIS & Nominatim (T-019).
 */

import { apiFetch } from "./api";
import type { components as CoreComponents } from "../types/api";

export type ReverseGeocodeResponse =
  CoreComponents["schemas"]["vistarae_core__schemas__poi__ReverseGeocodeResponse"];

export interface ForwardSearchResult {
  lat: number;
  lng: number;
  display_name: string;
  name: string;
  type: string;
  class: string;
  suggestedZoom: number;
  isSpecificLandmark: boolean;
}

/**
 * Calculates adaptive zoom level based on OSM feature class and type.
 * City/municipality: zoom 11-12. Specific landmark/building/viewpoint: zoom 16-18.
 */
export function calculateAdaptiveZoom(item: {
  class?: string;
  type?: string;
}): {
  zoom: number;
  isSpecificLandmark: boolean;
} {
  const c = item.class?.toLowerCase() || "";
  const t = item.type?.toLowerCase() || "";

  // Broad regions, countries, states, counties
  if (c === "boundary" || t === "country" || t === "state") {
    return { zoom: 6, isSpecificLandmark: false };
  }

  // Cities, towns, municipalities
  if (
    c === "place" &&
    ["city", "town", "administrative", "municipality", "county"].includes(t)
  ) {
    return { zoom: 11, isSpecificLandmark: false };
  }

  // Neighborhoods, suburbs
  if (["suburb", "neighbourhood", "quarter"].includes(t)) {
    return { zoom: 13, isSpecificLandmark: false };
  }

  // Specific landmarks, attractions, trails, buildings, viewpoints, amenities
  if (
    [
      "tourism",
      "historic",
      "leisure",
      "natural",
      "amenity",
      "building",
    ].includes(c) ||
    [
      "viewpoint",
      "attraction",
      "theme_park",
      "monument",
      "hotel",
      "peak",
    ].includes(t)
  ) {
    return { zoom: 17, isSpecificLandmark: true };
  }

  return { zoom: 14, isSpecificLandmark: false };
}

/**
 * Direct browser forward search against Nominatim with query-scoped adaptive zoom.
 */
export async function forwardSearch(
  query: string,
  limit: number = 5,
  signal?: AbortSignal,
): Promise<ForwardSearchResult[]> {
  if (!query || query.trim().length < 2) {
    return [];
  }

  const endpoint = `https://nominatim.openstreetmap.org/search?format=jsonv2&q=${encodeURIComponent(
    query.trim(),
  )}&limit=${limit}&addressdetails=1&accept-language=en`;

  try {
    const res = await fetch(endpoint, {
      signal,
      headers: {
        Accept: "application/json",
        "Accept-Language": "en",
      },
    });

    if (!res.ok) {
      return [];
    }

    const items = await res.json();
    return items.map((item: any) => {
      const { zoom, isSpecificLandmark } = calculateAdaptiveZoom(item);
      return {
        lat: parseFloat(item.lat),
        lng: parseFloat(item.lon),
        display_name: item.display_name,
        name: item.name || item.display_name.split(",")[0],
        type: item.type || "unknown",
        class: item.class || "unknown",
        suggestedZoom: zoom,
        isSpecificLandmark,
      };
    });
  } catch (err: any) {
    if (err.name === "AbortError") {
      return [];
    }
    console.warn("Direct forward search failed", err);
    return [];
  }
}

/**
 * Calls backend cached reverse geocode endpoint.
 */
export async function reverseGeocode(
  lat: number,
  lng: number,
  forceRefresh: boolean = false,
): Promise<ReverseGeocodeResponse> {
  const roundedLat = Math.round(lat * 100000) / 100000;
  const roundedLng = Math.round(lng * 100000) / 100000;
  const refreshParam = forceRefresh ? "&force_refresh=true" : "";
  return await apiFetch<ReverseGeocodeResponse>(
    `/api/pois/geocode/reverse?lat=${roundedLat}&lng=${roundedLng}${refreshParam}`,
  );
}

export interface ForwardGeocodeResponse {
  latitude: number | null;
  longitude: number | null;
  resolved_name?: string | null;
  street: string | null;
  city: string | null;
  locality?: string | null;
  state_province: string | null;
  admin_level_1?: string | null;
  admin_level_2?: string | null;
  country: string | null;
  country_code?: string | null;
  postal_code: string | null;
  cached: boolean;
}

/**
 * Calls backend cached forward geocode endpoint.
 */
export async function forwardGeocode(
  query: string,
  country?: string,
): Promise<ForwardGeocodeResponse> {
  const trimmed = query.trim();
  if (!trimmed) {
    return {
      latitude: null,
      longitude: null,
      street: null,
      city: null,
      state_province: null,
      country: null,
      postal_code: null,
      cached: false,
    };
  }
  const countryParam = country?.trim()
    ? `&country=${encodeURIComponent(country.trim())}`
    : "";
  return await apiFetch<ForwardGeocodeResponse>(
    `/api/pois/geocode/forward?q=${encodeURIComponent(trimmed)}${countryParam}`,
    { timeoutMs: 45000 },
  );
}

export interface ExtractUrlCoordinatesResponse {
  latitude: number | null;
  longitude: number | null;
  place_name: string | null;
  extraction_source: string;
  street: string | null;
  city: string | null;
  locality?: string | null;
  state_province: string | null;
  admin_level_1?: string | null;
  admin_level_2?: string | null;
  country: string | null;
  postal_code: string | null;
  country_code: string | null;
}

/**
 * Extracts coordinates and reverse-geocoded address from a webpage URL (Wikipedia, TripAdvisor, etc.).
 */
export async function extractCoordinatesFromUrl(
  url: string,
): Promise<ExtractUrlCoordinatesResponse> {
  return await apiFetch<ExtractUrlCoordinatesResponse>(
    `/api/pois/geocode/extract-url?url=${encodeURIComponent(url.trim())}`,
  );
}
