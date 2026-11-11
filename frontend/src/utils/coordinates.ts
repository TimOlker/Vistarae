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

// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { CoordinatePoint } from "../types/map";

const A = 6378245.0; // Krasovsky 1940 semi-major axis (meters)
const EE = 0.00669342162296594323; // First eccentricity squared
const X_PI = (Math.PI * 3000.0) / 180.0;

/**
 * Geographic bounding box defining mainland China.
 * Min Longitude: 73.66° E, Max Longitude: 135.05° E
 * Min Latitude: 18.16° N, Max Latitude: 53.55° N
 */
export const CHINA_BBOX = {
  minLng: 73.66,
  maxLng: 135.05,
  minLat: 18.16,
  maxLat: 53.55,
} as const;

/**
 * Checks whether a given coordinate point falls strictly within the China bounding box.
 *
 * Args:
 *   lng: Longitude in degrees.
 *   lat: Latitude in degrees.
 *
 * Returns:
 *   true if the coordinate is within China bounds; false otherwise.
 */
export function isInChinaBBox(lng: number, lat: number): boolean {
  return (
    lng >= CHINA_BBOX.minLng &&
    lng <= CHINA_BBOX.maxLng &&
    lat >= CHINA_BBOX.minLat &&
    lat <= CHINA_BBOX.maxLat
  );
}

function transformLat(x: number, y: number): number {
  let ret =
    -100.0 +
    2.0 * x +
    3.0 * y +
    0.2 * y * y +
    0.1 * x * y +
    0.2 * Math.sqrt(Math.abs(x));
  ret +=
    ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin((y / 3.0) * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((160.0 * Math.sin((y / 12.0) * Math.PI) +
      320.0 * Math.sin((y * Math.PI) / 30.0)) *
      2.0) /
    3.0;
  return ret;
}

function transformLng(x: number, y: number): number {
  let ret =
    300.0 +
    x +
    2.0 * y +
    0.1 * x * x +
    0.1 * x * y +
    0.1 * Math.sqrt(Math.abs(x));
  ret +=
    ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin((x / 3.0) * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((150.0 * Math.sin((x / 12.0) * Math.PI) +
      300.0 * Math.sin((x / 30.0) * Math.PI)) *
      2.0) /
    3.0;
  return ret;
}

/**
 * Transforms canonical WGS-84 coordinates to GCJ-02 (Mars coordinate system).
 * If the coordinates lie outside the China bounding box, returns unaltered coordinates.
 *
 * Args:
 *   lng: Canonical WGS-84 longitude.
 *   lat: Canonical WGS-84 latitude.
 *
 * Returns:
 *   CoordinatePoint with transformed or unaltered { lng, lat }.
 */
export function wgs84_to_gcj02(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }

  const dLatRaw = transformLat(lng - 105.0, lat - 35.0);
  const dLngRaw = transformLng(lng - 105.0, lat - 35.0);

  const radLat = (lat / 180.0) * Math.PI;
  let magic = Math.sin(radLat);
  magic = 1.0 - EE * magic * magic;
  const sqrtMagic = Math.sqrt(magic);

  const dLat =
    (dLatRaw * 180.0) / (((A * (1.0 - EE)) / (magic * sqrtMagic)) * Math.PI);
  const dLng =
    (dLngRaw * 180.0) / ((A / sqrtMagic) * Math.cos(radLat) * Math.PI);

  return {
    lng: lng + dLng,
    lat: lat + dLat,
  };
}

/**
 * Converts GCJ-02 coordinates back to canonical WGS-84 using Newton's numerical iteration method.
 * Iterates until the difference is below 0.000001° (< 0.1m ground resolution) or reaches 30 iterations.
 *
 * Args:
 *   lng: GCJ-02 longitude.
 *   lat: GCJ-02 latitude.
 *
 * Returns:
 *   CoordinatePoint with canonical WGS-84 { lng, lat }.
 */
export function gcj02_to_wgs84(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }

  let currWgsLng = lng;
  let currWgsLat = lat;
  const threshold = 1e-6; // 0.000001 degrees
  const maxIterations = 30;

  for (let i = 0; i < maxIterations; i++) {
    const projectedGcj = wgs84_to_gcj02(currWgsLng, currWgsLat);
    const dLng = projectedGcj.lng - lng;
    const dLat = projectedGcj.lat - lat;

    if (Math.abs(dLng) < threshold && Math.abs(dLat) < threshold) {
      break;
    }

    currWgsLng -= dLng;
    currWgsLat -= dLat;
  }

  return {
    lng: currWgsLng,
    lat: currWgsLat,
  };
}

/**
 * Converts GCJ-02 coordinates to Baidu BD-09 coordinates.
 */
export function gcj02_to_bd09(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }

  const z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * X_PI);
  const theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * X_PI);

  return {
    lng: z * Math.cos(theta) + 0.0065,
    lat: z * Math.sin(theta) + 0.006,
  };
}

/**
 * Converts Baidu BD-09 coordinates to GCJ-02 coordinates.
 */
export function bd09_to_gcj02(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }

  const x = lng - 0.0065;
  const y = lat - 0.006;
  const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * X_PI);
  const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * X_PI);

  return {
    lng: z * Math.cos(theta),
    lat: z * Math.sin(theta),
  };
}

/**
 * Converts canonical WGS-84 coordinates to Baidu BD-09 coordinates.
 */
export function wgs84_to_bd09(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }
  const gcj = wgs84_to_gcj02(lng, lat);
  return gcj02_to_bd09(gcj.lng, gcj.lat);
}

/**
 * Converts Baidu BD-09 coordinates back to canonical WGS-84 coordinates.
 */
export function bd09_to_wgs84(lng: number, lat: number): CoordinatePoint {
  if (!isInChinaBBox(lng, lat)) {
    return { lng, lat };
  }
  const gcj = bd09_to_gcj02(lng, lat);
  return gcj02_to_wgs84(gcj.lng, gcj.lat);
}

/**
 * Result of parsing a Google Maps URL.
 */
export interface GoogleMapsParseResult {
  lat: number;
  lng: number;
  placeName?: string;
}

/**
 * Detects whether the given text contains a Google Maps URL.
 */
export function isGoogleMapsUrl(text: string): boolean {
  if (!text || typeof text !== "string") return false;
  return /(?:google\.[a-z.]+\/maps|maps\.google\.[a-z.]+|goo\.gl\/maps|maps\.app\.goo\.gl)/i.test(
    text
  );
}

/**
 * Detects whether the given text contains a GeoHack URL.
 */
export function isGeohackUrl(text: string): boolean {
  if (!text || typeof text !== "string") return false;
  return /(?:geohack\.toolforge\.org|geohack\.php|geohack)/i.test(text);
}

/**
 * Detects whether the given text appears to be an arbitrary webpage URL (http:// or https:// or www.).
 */
export function isWebpageUrl(text: string): boolean {
  if (!text || typeof text !== "string") return false;
  const trimmed = text.trim();
  return (
    /^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(trimmed) ||
    /^www\.[a-z0-9-]+(?:\.[a-z0-9-]+)+/i.test(trimmed)
  );
}

/**
 * Extracts latitude, longitude, and place name from a Wikipedia GeoHack URL.
 */
export function parseGeohackUrl(text: string): GoogleMapsParseResult | null {
  if (!isGeohackUrl(text)) return null;

  try {
    // Extract pagename query param
    let placeName: string | undefined;
    const nameMatch = text.match(/[?&]pagename=([^&#]+)/i);
    if (nameMatch && nameMatch[1]) {
      try {
        placeName = decodeURIComponent(nameMatch[1].replace(/\+/g, " "))
          .replace(/_/g, " ")
          .trim();
      } catch {
        // ignore
      }
    }

    // Extract params query param
    const paramsMatch = text.match(/[?&]params=([^&#]+)/i);
    if (!paramsMatch || !paramsMatch[1]) return null;

    const rawParams = paramsMatch[1];

    // Format 1: DMS or decimal degrees with N/S and E/W e.g. 30.42187999_N_108.18389_E or 51_30_02_N_0_07_29_W
    const parts = rawParams.split("_");
    const nsIdx = parts.findIndex(
      (p) => p.toUpperCase() === "N" || p.toUpperCase() === "S"
    );
    const ewIdx = parts.findIndex(
      (p) => p.toUpperCase() === "E" || p.toUpperCase() === "W"
    );

    if (nsIdx !== -1 && ewIdx !== -1 && nsIdx < ewIdx) {
      const latParts = parts
        .slice(0, nsIdx)
        .map((x) => parseFloat(x))
        .filter((x) => !isNaN(x));
      const latSign = parts[nsIdx].toUpperCase() === "N" ? 1.0 : -1.0;
      let lat = 0;
      if (latParts.length === 1) lat = latParts[0] * latSign;
      else if (latParts.length === 2)
        lat = (latParts[0] + latParts[1] / 60.0) * latSign;
      else if (latParts.length >= 3)
        lat =
          (latParts[0] + latParts[1] / 60.0 + latParts[2] / 3600.0) * latSign;

      const lonParts = parts
        .slice(nsIdx + 1, ewIdx)
        .map((x) => parseFloat(x))
        .filter((x) => !isNaN(x));
      const lonSign = parts[ewIdx].toUpperCase() === "E" ? 1.0 : -1.0;
      let lng = 0;
      if (lonParts.length === 1) lng = lonParts[0] * lonSign;
      else if (lonParts.length === 2)
        lng = (lonParts[0] + lonParts[1] / 60.0) * lonSign;
      else if (lonParts.length >= 3)
        lng =
          (lonParts[0] + lonParts[1] / 60.0 + lonParts[2] / 3600.0) * lonSign;

      if (
        !isNaN(lat) &&
        !isNaN(lng) &&
        lat >= -90 &&
        lat <= 90 &&
        lng >= -180 &&
        lng <= 180
      ) {
        return { lat, lng, placeName };
      }
    }

    // Format 2: Decimal separated by ; or _ e.g. 40.7128;-74.0060 or 40.7128_-74.0060 (no N/S/E/W)
    if (!/[NSEW]/i.test(rawParams)) {
      const decMatch = rawParams.match(
        /^(-?\d+(?:\.\d+)?)[;_](-?\d+(?:\.\d+)?)/
      );
      if (decMatch) {
        const lat = parseFloat(decMatch[1]);
        const lng = parseFloat(decMatch[2]);
        if (
          !isNaN(lat) &&
          !isNaN(lng) &&
          lat >= -90 &&
          lat <= 90 &&
          lng >= -180 &&
          lng <= 180
        ) {
          return { lat, lng, placeName };
        }
      }
    }
  } catch (err) {
    console.debug("Failed parsing geohack url", err);
  }

  return null;
}

/**
 * Extracts latitude, longitude, and optional place name from a Google Maps URL or text containing one.
 *
 * Supports various formats:
 * - Data parameter pins (!3d<lat>!4d<lng> or !4d<lng>!3d<lat> or !2d<lng>!3d<lat>)
 * - Place/Search coordinate paths (/maps/place/<lat>,<lng> or /maps/search/<lat>,<lng>)
 * - Viewport coordinates (@<lat>,<lng>)
 * - Query parameters (?q=<lat>,<lng>, ?ll=<lat>,<lng>, ?daddr=<lat>,<lng>, etc.)
 * - Directions paths (/maps/dir/.../<lat>,<lng>)
 */
export function parseGoogleMapsUrl(text: string): GoogleMapsParseResult | null {
  if (!isGoogleMapsUrl(text)) {
    return null;
  }

  const validateCoords = (
    lat: number,
    lng: number,
    placeName?: string
  ): GoogleMapsParseResult | null => {
    if (
      !isNaN(lat) &&
      !isNaN(lng) &&
      lat >= -90 &&
      lat <= 90 &&
      lng >= -180 &&
      lng <= 180 &&
      !(lat === 0 && lng === 0)
    ) {
      return { lat, lng, placeName };
    }
    return null;
  };

  // 1. Extract place name if present in URL (/maps/place/<name>/)
  let placeName: string | undefined;
  const placeMatch = text.match(/\/maps\/place\/([^/@?]+)/i);
  if (placeMatch && placeMatch[1]) {
    try {
      const raw = decodeURIComponent(placeMatch[1].replace(/\+/g, " "));
      if (!/^-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?$/.test(raw.trim())) {
        placeName = raw.trim();
      }
    } catch {
      // ignore URI decode error
    }
  }

  // 2. Exact pin coordinates in data parameter: !3d<lat>!4d<lng>
  // e.g. !3m5!1s0x...!8m2!3d32.4727002!4d3.7082024!16s...
  const pin3d4d = text.match(/!3d(-?\d+(?:\.\d+)?).*?!4d(-?\d+(?:\.\d+)?)/);
  if (pin3d4d) {
    const res = validateCoords(
      parseFloat(pin3d4d[1]),
      parseFloat(pin3d4d[2]),
      placeName
    );
    if (res) return res;
  }

  // Check reversed !4d<lng>!3d<lat>
  const pin4d3d = text.match(/!4d(-?\d+(?:\.\d+)?).*?!3d(-?\d+(?:\.\d+)?)/);
  if (pin4d3d) {
    const res = validateCoords(
      parseFloat(pin4d3d[2]),
      parseFloat(pin4d3d[1]),
      placeName
    );
    if (res) return res;
  }

  // Embed format: !2d<lng>!3d<lat>
  const embed2d3d = text.match(/!2d(-?\d+(?:\.\d+)?).*?!3d(-?\d+(?:\.\d+)?)/);
  if (embed2d3d) {
    const res = validateCoords(
      parseFloat(embed2d3d[2]),
      parseFloat(embed2d3d[1]),
      placeName
    );
    if (res) return res;
  }

  // 3. Direct coordinates in path: /maps/place/<lat>,<lng> or /maps/search/<lat>,<lng>
  const pathMatch = text.match(
    /\/maps\/(?:place|search)\/(-?\d+(?:\.\d+)?)(?:%20|%2C|[,\s+])+(-?\d+(?:\.\d+)?)/i
  );
  if (pathMatch) {
    const res = validateCoords(
      parseFloat(pathMatch[1]),
      parseFloat(pathMatch[2]),
      placeName
    );
    if (res) return res;
  }

  // 4. Query parameters: q, query, ll, sll, center, destination, daddr
  const queryParamMatch = text.match(
    /[?&](?:q|query|ll|sll|center|destination|daddr)=(?:loc:)?(-?\d+(?:\.\d+)?)(?:%20|\+|,)+(-?\d+(?:\.\d+)?)/i
  );
  if (queryParamMatch) {
    const res = validateCoords(
      parseFloat(queryParamMatch[1]),
      parseFloat(queryParamMatch[2]),
      placeName
    );
    if (res) return res;
  }

  // 5. Viewport / Camera center coordinates: @<lat>,<lng>
  const atMatch = text.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (atMatch) {
    const res = validateCoords(
      parseFloat(atMatch[1]),
      parseFloat(atMatch[2]),
      placeName
    );
    if (res) return res;
  }

  // 6. Directions destination coordinates: /maps/dir/.../<lat>,<lng>
  const dirMatch = text.match(
    /\/maps\/dir\/(?:.*?\/)?(-?\d+(?:\.\d+)?)(?:%20|%2C|[,\s+])+(-?\d+(?:\.\d+)?)/i
  );
  if (dirMatch) {
    const res = validateCoords(
      parseFloat(dirMatch[1]),
      parseFloat(dirMatch[2]),
      placeName
    );
    if (res) return res;
  }

  // 7. Fallback: Any coordinate pair in the text matching standard coordinate precision
  const genericCoords = text.match(
    /(-?\d{1,2}\.\d{3,})(?:%20|%2C|[,\s+])+(-?\d{1,3}\.\d{3,})/
  );
  if (genericCoords) {
    const res = validateCoords(
      parseFloat(genericCoords[1]),
      parseFloat(genericCoords[2]),
      placeName
    );
    if (res) return res;
  }

  // If URL had a place name but no parseable coordinates, return placeName with NaN coordinates
  if (placeName) {
    return { lat: NaN, lng: NaN, placeName };
  }

  return null;
}

export const COUNTRY_TO_ISO_MAP: Record<string, string> = {
  yemen: "YE",
  "united states": "US",
  usa: "US",
  us: "US",
  "united kingdom": "GB",
  uk: "GB",
  england: "GB",
  scotland: "GB",
  wales: "GB",
  "northern ireland": "GB",
  italy: "IT",
  france: "FR",
  germany: "DE",
  spain: "ES",
  japan: "JP",
  china: "CN",
  "south korea": "KR",
  korea: "KR",
  hungary: "HU",
  ethiopia: "ET",
  ireland: "IE",
  norway: "NO",
  "ivory coast": "CI",
  "côte d'ivoire": "CI",
  venezuela: "VE",
  "south africa": "ZA",
  haiti: "HT",
  egypt: "EG",
  honduras: "HN",
  syria: "SY",
  jordan: "JO",
  india: "IN",
  canada: "CA",
  mexico: "MX",
  australia: "AU",
  "new zealand": "NZ",
  brazil: "BR",
  argentina: "AR",
  chile: "CL",
  peru: "PE",
  colombia: "CO",
  greece: "GR",
  turkey: "TR",
  türkiye: "TR",
  switzerland: "CH",
  austria: "AT",
  netherlands: "NL",
  belgium: "BE",
  portugal: "PT",
  sweden: "SE",
  denmark: "DK",
  finland: "FI",
  iceland: "IS",
  morocco: "MA",
  algeria: "DZ",
  tunisia: "TN",
  tanzania: "TZ",
  kenya: "KE",
  uganda: "UG",
  rwanda: "RW",
  thailand: "TH",
  vietnam: "VN",
  indonesia: "ID",
  malaysia: "MY",
  philippines: "PH",
  singapore: "SG",
  cambodia: "KH",
  laos: "LA",
  nepal: "NP",
  "sri lanka": "LK",
  "saudi arabia": "SA",
  "united arab emirates": "AE",
  uae: "AE",
  oman: "OM",
  qatar: "QA",
  israel: "IL",
  croatia: "HR",
  "czech republic": "CZ",
  czechia: "CZ",
  poland: "PL",
  namibia: "NA",
  monaco: "MC",
  mongolia: "MN",
  montenegro: "ME",
  "monte negro": "ME",
  mozambique: "MZ",
  myanmar: "MM",
  burma: "MM",
  botswana: "BW",
  zimbabwe: "ZW",
  zambia: "ZM",
  madagascar: "MG",
  ghana: "GH",
  senegal: "SN",
  nigeria: "NG",
  angola: "AO",
  benin: "BJ",
  "burkina faso": "BF",
  burundi: "BI",
  cameroon: "CM",
  "cape verde": "CV",
  "cabo verde": "CV",
  chad: "TD",
  congo: "CG",
  "dr congo": "CD",
  "democratic republic of the congo": "CD",
  djibouti: "DJ",
  eswatini: "SZ",
  swaziland: "SZ",
  gabon: "GA",
  gambia: "GM",
  guinea: "GN",
  lesotho: "LS",
  liberia: "LR",
  libya: "LY",
  malawi: "MW",
  mali: "ML",
  mauritania: "MR",
  mauritius: "MU",
  niger: "NE",
  seychelles: "SC",
  "sierra leone": "SL",
  somalia: "SO",
  "south sudan": "SS",
  sudan: "SD",
  togo: "TG",
  albania: "AL",
  andorra: "AD",
  armenia: "AM",
  azerbaijan: "AZ",
  bahamas: "BS",
  bahrain: "BH",
  bangladesh: "BD",
  barbados: "BB",
  belarus: "BY",
  belize: "BZ",
  bhutan: "BT",
  bolivia: "BO",
  "bosnia and herzegovina": "BA",
  bosnia: "BA",
  brunei: "BN",
  bulgaria: "BG",
  "costa rica": "CR",
  cuba: "CU",
  cyprus: "CY",
  "dominican republic": "DO",
  ecuador: "EC",
  "el salvador": "SV",
  estonia: "EE",
  fiji: "FJ",
  georgia: "GE",
  guatemala: "GT",
  guyana: "GY",
  iran: "IR",
  iraq: "IQ",
  jamaica: "JM",
  kazakhstan: "KZ",
  kuwait: "KW",
  kyrgyzstan: "KG",
  latvia: "LV",
  lebanon: "LB",
  liechtenstein: "LI",
  lithuania: "LT",
  luxembourg: "LU",
  maldives: "MV",
  malta: "MT",
  moldova: "MD",
  nicaragua: "NI",
  "north korea": "KP",
  "north macedonia": "MK",
  macedonia: "MK",
  pakistan: "PK",
  palestine: "PS",
  panama: "PA",
  "papua new guinea": "PG",
  paraguay: "PY",
  romania: "RO",
  russia: "RU",
  "russian federation": "RU",
  serbia: "RS",
  slovakia: "SK",
  slovenia: "SI",
  suriname: "SR",
  taiwan: "TW",
  tajikistan: "TJ",
  "trinidad and tobago": "TT",
  turkmenistan: "TM",
  ukraine: "UA",
  uruguay: "UY",
  uzbekistan: "UZ",
  "vatican city": "VA",
  "hong kong": "HK",
  macau: "MO",
};

/**
 * Resolves a country name to its ISO 3166-1 alpha-2 country code.
 */
export function countryNameToIsoCode(name: string | null | undefined): string | null {
  if (!name) return null;
  const clean = name.trim().toLowerCase();
  if (clean.length === 2 && /^[a-z]{2}$/.test(clean)) {
    return clean.toUpperCase();
  }
  return COUNTRY_TO_ISO_MAP[clean] || null;
}
