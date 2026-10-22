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

export interface BulkOperationResponse {
  modified_count: number;
}

export interface BulkDeleteResponse {
  deleted_count: number;
}

/**
 * Executes an atomic bulk edit mutation across selected POIs (REQ-MAIN-027 to REQ-MAIN-035).
 */
export async function bulkEditPois(
  poiIds: string[],
  action: string,
  payload: any,
): Promise<BulkOperationResponse> {
  return apiFetch<BulkOperationResponse>("/api/pois/bulk-edit", {
    method: "POST",
    body: JSON.stringify({
      poi_ids: poiIds,
      action,
      payload,
    }),
  });
}

/**
 * Executes atomic bulk deletion across selected POIs (REQ-MAIN-034, REQ-MAIN-035).
 */
export async function bulkDeletePois(
  poiIds: string[],
): Promise<BulkDeleteResponse> {
  return apiFetch<BulkDeleteResponse>("/api/pois/bulk-delete", {
    method: "POST",
    body: JSON.stringify({
      poi_ids: poiIds,
    }),
  });
}
