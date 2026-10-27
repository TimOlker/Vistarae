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
import type { components } from "../types/user-context-api";

export type TravelStyleResponse = components["schemas"]["TravelStyleResponse"];
export type TravelStyleUpdateRequest = components["schemas"]["TravelStyleUpdateRequest"];
export type UserPromptItem = components["schemas"]["UserPromptItem"];

export const userContextService = {
  /**
   * Fetches the saved travel style narrative and active decomposed prompt directives.
   */
  async getTravelStyle(): Promise<TravelStyleResponse> {
    return apiFetch<TravelStyleResponse>("/api/user/profile/travel-style", {
      method: "GET",
    });
  },

  /**
   * Updates the travel style narrative and triggers AI decomposition of prompt directives.
   */
  async updateTravelStyle(
    travelStyleDescription: string | null,
  ): Promise<TravelStyleResponse> {
    const payload: TravelStyleUpdateRequest = {
      travel_style_description: travelStyleDescription,
    };
    return apiFetch<TravelStyleResponse>("/api/user/profile/travel-style", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  },

  /**
   * Clears the travel style narrative and removes custom prompt directives.
   */
  async clearTravelStyle(): Promise<TravelStyleResponse> {
    return apiFetch<TravelStyleResponse>("/api/user/profile/travel-style", {
      method: "DELETE",
    });
  },
};
