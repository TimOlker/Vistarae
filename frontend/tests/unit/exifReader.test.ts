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

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  extractPhotoEXIF,
  cleanupPhotoPreview,
} from "../../src/utils/exifReader";
import ExifReader from "exifreader";

vi.mock("exifreader", () => ({
  default: {
    load: vi.fn(),
  },
}));

describe("Client-Only Photo EXIF Reader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.URL.createObjectURL = vi
      .fn()
      .mockReturnValue("blob:http://localhost:5173/mock-uuid");
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  it("extracts GPS and timestamp metadata when present in file buffer", async () => {
    const mockFile = new File(["mock-image-data"], "travel_beijing.jpg", {
      type: "image/jpeg",
    });
    mockFile.arrayBuffer = vi.fn().mockResolvedValue(new ArrayBuffer(16));

    (ExifReader.load as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      gps: {
        Latitude: 39.909187,
        Longitude: 116.397458,
      },
      exif: {
        DateTimeOriginal: { description: "2026:10:19 14:30:00" },
        Orientation: { value: 1 },
      },
    });

    const metadata = await extractPhotoEXIF(mockFile);

    expect(metadata.fileName).toBe("travel_beijing.jpg");
    expect(metadata.hasGps).toBe(true);
    expect(metadata.latitude).toBe(39.909187);
    expect(metadata.longitude).toBe(116.397458);
    expect(metadata.capturedAt).toBe("2026-10-19T14:30:00Z");
    expect(metadata.previewUrl).toBe("blob:http://localhost:5173/mock-uuid");
  });

  it("handles photos with absent or privacy-stripped GPS metadata gracefully", async () => {
    const mockFile = new File(["mock-png-data"], "screenshot.png", {
      type: "image/png",
    });
    mockFile.arrayBuffer = vi.fn().mockResolvedValue(new ArrayBuffer(16));

    (ExifReader.load as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      exif: {},
    });

    const metadata = await extractPhotoEXIF(mockFile);

    expect(metadata.fileName).toBe("screenshot.png");
    expect(metadata.hasGps).toBe(false);
    expect(metadata.latitude).toBeNull();
    expect(metadata.longitude).toBeNull();
  });

  it("revokes ephemeral Blob URLs on cleanupPhotoPreview", () => {
    const previewUrl = "blob:http://localhost:5173/ephemeral-preview-123";
    cleanupPhotoPreview(previewUrl);

    expect(globalThis.URL.revokeObjectURL).toHaveBeenCalledWith(previewUrl);
  });
});
