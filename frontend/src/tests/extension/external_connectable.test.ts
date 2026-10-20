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

import { describe, it, expect, beforeEach, vi } from "vitest";
import { openLocalFolder } from "../../services/nativeHostService";

describe("SPA-to-Extension Bridge & Graceful Degradation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // @ts-ignore
    delete (window as any).chrome;
  });

  it("returns actionable install banner when Chrome extension is not present in browser", async () => {
    const result = await openLocalFolder("/photos/yosemite");
    expect(result.success).toBe(false);
    expect(result.code).toBe("EXTENSION_NOT_INSTALLED");
    expect(result.toastMessage).toContain(
      "Vistarae Extension required for local folder opening",
    );
  });

  it("returns installation banner if chrome.runtime.lastError occurs during message dispatch", async () => {
    // @ts-ignore
    (window as any).chrome = {
      runtime: {
        lastError: {
          message:
            "Could not establish connection. Receiving end does not exist.",
        },
        sendMessage: vi.fn((_extId, _msg, cb) => {
          cb(null);
        }),
      },
    };

    const result = await openLocalFolder("/photos/yosemite");
    expect(result.success).toBe(false);
    expect(result.code).toBe("EXTENSION_COMMUNICATION_FAILED");
    expect(result.toastMessage).toContain(
      "Vistarae Extension required for local folder opening",
    );
  });

  it("returns registration toast when native messaging host is not installed on system", async () => {
    // @ts-ignore
    (window as any).chrome = {
      runtime: {
        lastError: null,
        sendMessage: vi.fn((_extId, _msg, cb) => {
          cb({
            success: false,
            error: {
              type: "native_host_not_found",
              title: "Native Host Not Available",
              status: 404,
              detail:
                "Specified native messaging host not found: com.vistarae.folder_opener",
            },
          });
        }),
      },
    };

    const result = await openLocalFolder("/photos/yosemite");
    expect(result.success).toBe(false);
    expect(result.toastMessage).toBe(
      "Run python scripts/register_native_host.py to register folder opener.",
    );
  });

  it("resolves success: true when folder is launched by native host", async () => {
    // @ts-ignore
    (window as any).chrome = {
      runtime: {
        lastError: null,
        sendMessage: vi.fn((_extId, _msg, cb) => {
          cb({
            success: true,
            data: {
              status: "ok",
              action: "open_folder",
              path: "C:\\Photos\\Yosemite",
            },
          });
        }),
      },
    };

    const result = await openLocalFolder("C:\\Photos\\Yosemite");
    expect(result.success).toBe(true);
    expect(result.toastMessage).toContain(
      "Opened folder: C:\\Photos\\Yosemite",
    );
  });
});
