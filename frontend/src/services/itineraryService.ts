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
 * Itinerary API client service (T015, T029).
 * Provides typed communication with backend /api/itineraries/* endpoints.
 */

import { apiFetch } from "./api";
import type { components } from "../types/api";

export type ItinerarySummary = components["schemas"]["ItinerarySummary"];
export type ItineraryResponse = components["schemas"]["ItineraryResponse"];
export type ItineraryDayResponse = components["schemas"]["ItineraryDayResponse"];
export type ItineraryItemResponse = components["schemas"]["ItineraryItemResponse"];
export type ItineraryCreate = components["schemas"]["ItineraryCreate"];
export type ItineraryUpdate = components["schemas"]["ItineraryUpdate"];
export type ItineraryGenerateRequest = components["schemas"]["ItineraryGenerateRequest"];
export type ItineraryItemReorderRequest = components["schemas"]["ItineraryItemReorderRequest"];
export type CircuitBreakerWarning = components["schemas"]["CircuitBreakerWarning"];
export type MissingMealAdvisory = components["schemas"]["MissingMealAdvisory"];

export interface ImportPoiRequest {
  name: string;
  lat: number;
  lng: number;
  description?: string | null;
  category?: string;
  estimated_cost?: number | null;
}

export const itineraryService = {
  /**
   * Lists all travel itineraries belonging to the authenticated user.
   */
  async listItineraries(): Promise<ItinerarySummary[]> {
    return apiFetch<ItinerarySummary[]>("/api/itineraries", {
      method: "GET",
    });
  },

  /**
   * Retrieves full details of a specific itinerary by ID.
   */
  async getItinerary(id: string): Promise<ItineraryResponse> {
    return apiFetch<ItineraryResponse>(`/api/itineraries/${id}`, {
      method: "GET",
    });
  },

  /**
   * Manually creates a new travel itinerary.
   */
  async createItinerary(payload: ItineraryCreate): Promise<ItineraryResponse> {
    return apiFetch<ItineraryResponse>("/api/itineraries", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Synthesizes an itinerary draft using hybrid PostGIS + pgvector RAG.
   */
  async generateItinerary(payload: ItineraryGenerateRequest): Promise<ItineraryResponse> {
    return apiFetch<ItineraryResponse>("/api/itineraries/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Updates itinerary metadata (title, dates, budget, status).
   */
  async updateItinerary(id: string, payload: ItineraryUpdate): Promise<ItineraryResponse> {
    return apiFetch<ItineraryResponse>(`/api/itineraries/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Deletes an itinerary and cascades to all child days and items.
   */
  async deleteItinerary(id: string): Promise<void> {
    await apiFetch<void>(`/api/itineraries/${id}`, {
      method: "DELETE",
    });
  },

  /**
   * Batch reorders scheduled items across days and time slots.
   */
  async reorderItems(
    id: string,
    payload: ItineraryItemReorderRequest
  ): Promise<ItineraryResponse> {
    return apiFetch<ItineraryResponse>(`/api/itineraries/${id}/items/reorder`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Imports an AI-recommended or manual itinerary POI into the user's permanent POI collection.
   */
  async importPoiToSaved(poi: ImportPoiRequest): Promise<{ id: string; name: string }> {
    return apiFetch<{ id: string; name: string }>("/api/pois", {
      method: "POST",
      body: JSON.stringify({
        name: poi.name,
        geom: {
          lat: poi.lat,
          lon: poi.lng,
        },
        description: poi.description ?? undefined,
        creation_metadata: {
          source: "itinerary_ai_import",
          category: poi.category ?? "attraction",
        },
      }),
    });
  },
};
