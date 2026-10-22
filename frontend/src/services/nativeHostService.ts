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

export interface NativeHostResult {
  success: boolean;
  error?: string;
  code?: string;
  toastMessage?: string;
}

/**
 * Default Extension ID for Vistarae Chrome Extension (can be customized via VITE_VISTARAE_EXTENSION_ID)
 */
export const DEFAULT_EXTENSION_ID = "ekafkcbddmcmflnbgnlkaebpllpnjggk";

/**
 * Requests the Chrome Extension to open a local directory or private UNC share via native messaging.
 * Gracefully degrades with actionable toast instructions if the extension or native host is missing.
 *
 * @param {string} path - Local path, file:/// URI, or private UNC network path.
 * @param {string} [extensionId] - Optional extension ID override.
 * @returns {Promise<NativeHostResult>}
 */
export async function openLocalFolder(
  path: string,
  extensionId?: string,
): Promise<NativeHostResult> {
  const targetExtensionId =
    extensionId ||
    (typeof import.meta !== "undefined" &&
      (import.meta as any).env?.VITE_VISTARAE_EXTENSION_ID) ||
    DEFAULT_EXTENSION_ID;

  // Check if Chrome extension runtime API is present in browser
  const chromeRuntime = (window as any).chrome?.runtime;
  if (!chromeRuntime || !chromeRuntime.sendMessage) {
    return {
      success: false,
      code: "EXTENSION_NOT_INSTALLED",
      toastMessage:
        "Vistarae Extension required for local folder opening. Click to install.",
    };
  }

  return new Promise((resolve) => {
    try {
      chromeRuntime.sendMessage(
        targetExtensionId,
        { action: "open_folder", path },
        (response: any) => {
          const lastError = chromeRuntime.lastError;
          if (lastError) {
            resolve({
              success: false,
              code: "EXTENSION_COMMUNICATION_FAILED",
              toastMessage:
                "Vistarae Extension required for local folder opening. Click to install.",
              error: lastError.message,
            });
            return;
          }

          if (response?.success) {
            resolve({
              success: true,
              toastMessage: `Opened folder: ${path}`,
            });
          } else {
            const err = response?.error;
            let toast = err?.detail || "Failed to open local folder.";
            if (err?.type === "native_host_not_found") {
              toast =
                "Run python scripts/register_native_host.py to register folder opener.";
            }

            resolve({
              success: false,
              code: err?.code || err?.type || "NATIVE_HOST_ERROR",
              error: err?.detail,
              toastMessage: toast,
            });
          }
        },
      );
    } catch (err: any) {
      resolve({
        success: false,
        code: "DISPATCH_EXCEPTION",
        error: err.message,
        toastMessage: "Error communicating with Vistarae Chrome Extension.",
      });
    }
  });
}
