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
 * Layout modes supported by the main workspace layout (REQ-MAIN-001).
 *
 * - 'split': Map and Table share horizontal space side-by-side (58% / 42%).
 * - 'map_only': Map occupies 100% width, Table is hidden.
 * - 'table_only': Table occupies 100% width, Map is hidden.
 */
export type LayoutMode = "split" | "map_only" | "table_only";

export interface ViewModeOption {
  mode: LayoutMode;
  label: string;
  ariaLabel: string;
  tooltip: string;
}
