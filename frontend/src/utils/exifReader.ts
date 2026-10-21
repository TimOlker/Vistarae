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

import ExifReader from "exifreader";

export interface ExtractedPhotoMetadata {
  fileName: string;
  fileSizeBytes: number;
  mimeType: string;
  hasGps: boolean;
  latitude: number | null; // Canonical WGS-84 (-90.0 to 90.0)
  longitude: number | null; // Canonical WGS-84 (-180.0 to 180.0)
  capturedAt: string | null; // ISO 8601 string or date
  orientation: number | null;
  previewUrl: string; // Ephemeral Blob URL generated via URL.createObjectURL
}

/**
 * Parses GPS and timestamp metadata from a photo file entirely in browser memory.
 * Emits zero outbound network bytes to external services (Constitution Operational Invariant 3).
 *
 * Args:
 *   file: The browser File object (JPEG, WebP, PNG, HEIC/HEIF).
 *
 * Returns:
 *   ExtractedPhotoMetadata with canonical WGS-84 coordinates and ephemeral preview URL.
 */
export async function extractPhotoEXIF(
  file: File,
): Promise<ExtractedPhotoMetadata> {
  const previewUrl = URL.createObjectURL(file);

  try {
    const arrayBuffer = await file.arrayBuffer();
    const tags = ExifReader.load(arrayBuffer, { expanded: true });

    let latitude: number | null = null;
    let longitude: number | null = null;
    let hasGps = false;

    if (
      tags.gps &&
      typeof tags.gps.Latitude === "number" &&
      typeof tags.gps.Longitude === "number"
    ) {
      latitude = tags.gps.Latitude;
      longitude = tags.gps.Longitude;
      hasGps = true;
    }

    // Capture date formatting
    let capturedAt: string | null = null;
    const dateTag = tags.exif?.DateTimeOriginal || tags.exif?.DateTimeDigitized;
    if (dateTag && dateTag.description) {
      // EXIF date format is usually "YYYY:MM:DD HH:MM:SS"
      const parts = dateTag.description.match(
        /^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})/,
      );
      if (parts) {
        capturedAt = `${parts[1]}-${parts[2]}-${parts[3]}T${parts[4]}:${parts[5]}:${parts[6]}Z`;
      } else {
        capturedAt = dateTag.description;
      }
    }

    const orientation = tags.exif?.Orientation?.value
      ? Number(tags.exif.Orientation.value)
      : null;

    return {
      fileName: file.name,
      fileSizeBytes: file.size,
      mimeType: file.type || "image/jpeg",
      hasGps,
      latitude,
      longitude,
      capturedAt,
      orientation,
      previewUrl,
    };
  } catch (err) {
    // If parsing fails or EXIF is corrupted/absent, return clean metadata with fallback
    return {
      fileName: file.name,
      fileSizeBytes: file.size,
      mimeType: file.type || "image/jpeg",
      hasGps: false,
      latitude: null,
      longitude: null,
      capturedAt: null,
      orientation: null,
      previewUrl,
    };
  }
}

/**
 * Reclaims ephemeral Blob memory allocated by URL.createObjectURL.
 * Must be invoked when the modal dialog closes or photo is replaced.
 */
export function cleanupPhotoPreview(previewUrl?: string | null) {
  if (previewUrl && previewUrl.startsWith("blob:")) {
    URL.revokeObjectURL(previewUrl);
  }
}
