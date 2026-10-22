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
import type {
  FilterRule,
  FilterRuleCreateRequest,
  FilterRuleListResponse,
  FilterRuleUpdateRequest,
  QueryGroup,
} from "../types/filter";
import type { POIMapFeature } from "../types/map";

export const filterRuleService = {
  /**
   * Retrieves all saved filter rules owned by current user.
   */
  async listFilterRules(): Promise<FilterRuleListResponse> {
    return apiFetch<FilterRuleListResponse>("/api/pois/filter-rules", {
      method: "GET",
    });
  },

  /**
   * Retrieves a single saved filter rule by ID.
   */
  async getFilterRule(id: string): Promise<FilterRule> {
    return apiFetch<FilterRule>(`/api/pois/filter-rules/${id}`, {
      method: "GET",
    });
  },

  /**
   * Persists a new named filter rule (throws 409 Conflict if name exists).
   */
  async createFilterRule(
    payload: FilterRuleCreateRequest,
  ): Promise<FilterRule> {
    return apiFetch<FilterRule>("/api/pois/filter-rules", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Updates/overwrites an existing filter rule.
   */
  async updateFilterRule(
    id: string,
    payload: FilterRuleUpdateRequest,
  ): Promise<FilterRule> {
    return apiFetch<FilterRule>(`/api/pois/filter-rules/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Deletes a filter rule by ID.
   */
  async deleteFilterRule(id: string): Promise<void> {
    await apiFetch<void>(`/api/pois/filter-rules/${id}`, {
      method: "DELETE",
    });
  },

  /**
   * Evaluates a structured query tree on the backend against server dataset.
   */
  async queryPois(
    queryTree: QueryGroup,
    bbox?: string,
    limit = 100,
    offset = 0,
  ): Promise<{ items: POIMapFeature[]; total: number }> {
    const payload = {
      query_tree: queryTree,
      bbox,
    };
    const res = await apiFetch<{ items: any[]; total: number }>(
      `/api/pois/query?limit=${limit}&offset=${offset}`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );

    // Map response items to POIMapFeature format
    const mappedItems: POIMapFeature[] = (res.items || []).map((p: any) => ({
      id: p.id,
      name: p.name,
      canonical_lng: p.lon,
      canonical_lat: p.lat,
      render_lng: p.lon,
      render_lat: p.lat,
      visit_state: p.visit_state || "not_visited",
      rating: p.rating,
      tags: (p.tags || []).map((t: any) =>
        typeof t === "string" ? t : t.name,
      ),
      city: p.city || undefined,
      state: p.states?.[0] || undefined,
      country: p.countries?.[0] || undefined,
      parent_poi_id: p.parent_poi_id,
      already_visited: p.already_visited,
      visit_pending: p.visit_pending,
      want_to_visit_again: p.want_to_visit_again,
    }));

    return {
      items: mappedItems,
      total: res.total,
    };
  },
};

export const listFilterRules =
  filterRuleService.listFilterRules.bind(filterRuleService);
export const getFilterRule =
  filterRuleService.getFilterRule.bind(filterRuleService);
export const createFilterRule =
  filterRuleService.createFilterRule.bind(filterRuleService);
export const updateFilterRule =
  filterRuleService.updateFilterRule.bind(filterRuleService);
export const deleteFilterRule =
  filterRuleService.deleteFilterRule.bind(filterRuleService);
export const queryPois = filterRuleService.queryPois.bind(filterRuleService);
export default filterRuleService;
