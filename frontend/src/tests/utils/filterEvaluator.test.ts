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

import { describe, it, expect } from "vitest";
import {
  evaluateQueryTree,
  evaluateRuleClause,
  filterPOIsInMemory,
} from "../../utils/filterEvaluator";
import type { QueryGroup } from "../../types/filter";
import type { POIMapFeature } from "../../types/map";

const testPOIs: POIMapFeature[] = [
  {
    id: "p1",
    name: "Senso-ji Temple",
    canonical_lng: 139.7966,
    canonical_lat: 35.7147,
    render_lng: 139.7966,
    render_lat: 35.7147,
    city: "Tokyo",
    country: "Japan",
    rating: 5,
    visit_state: "visited_return",
    already_visited: true,
    visit_pending: false,
    tags: ["temple", "historic"],
  },
  {
    id: "p2",
    name: "Fushimi Inari Taisha",
    canonical_lng: 135.7726,
    canonical_lat: 34.9671,
    render_lng: 135.7726,
    render_lat: 34.9671,
    city: "Kyoto",
    country: "Japan",
    rating: 4,
    visit_state: "not_visited",
    already_visited: false,
    visit_pending: true,
    tags: ["shrine", "scenic"],
  },
  {
    id: "p3",
    name: "Louvre Museum",
    canonical_lng: 2.3376,
    canonical_lat: 48.8606,
    render_lng: 2.3376,
    render_lat: 48.8606,
    city: "Paris",
    country: "France",
    rating: 5,
    visit_state: "not_visited",
    already_visited: false,
    visit_pending: true,
    tags: ["museum", "art"],
  },
];

describe("Client-side Filter Evaluator (T-019 / REQ-MAIN-009, REQ-MAIN-010)", () => {
  it("evaluates city and country clauses correctly", () => {
    expect(
      evaluateRuleClause(testPOIs[0], {
        id: "1",
        field: "city",
        operator: "equals",
        value: "tokyo",
      }),
    ).toBe(true);
    expect(
      evaluateRuleClause(testPOIs[0], {
        id: "2",
        field: "city",
        operator: "equals",
        value: "Kyoto",
      }),
    ).toBe(false);
    expect(
      evaluateRuleClause(testPOIs[0], {
        id: "3",
        field: "city",
        operator: "contains",
        value: "ok",
      }),
    ).toBe(true);
    expect(
      evaluateRuleClause(testPOIs[0], {
        id: "4",
        field: "country",
        operator: "equals",
        value: "Japan",
      }),
    ).toBe(true);
  });

  it("evaluates rating comparison operators", () => {
    expect(
      evaluateRuleClause(testPOIs[0], {
        id: "1",
        field: "rating",
        operator: ">=",
        value: 5,
      }),
    ).toBe(true);
    expect(
      evaluateRuleClause(testPOIs[1], {
        id: "2",
        field: "rating",
        operator: ">=",
        value: 5,
      }),
    ).toBe(false);
    expect(
      evaluateRuleClause(testPOIs[1], {
        id: "3",
        field: "rating",
        operator: "<",
        value: 5,
      }),
    ).toBe(true);
  });

  it("evaluates tags with has_tag and lacks_tag", () => {
    expect(
      evaluateRuleClause(testPOIs[0], {
        id: "1",
        field: "tag",
        operator: "has_tag",
        value: "historic",
      }),
    ).toBe(true);
    expect(
      evaluateRuleClause(testPOIs[0], {
        id: "2",
        field: "tag",
        operator: "has_tag",
        value: "museum",
      }),
    ).toBe(false);
    expect(
      evaluateRuleClause(testPOIs[0], {
        id: "3",
        field: "tag",
        operator: "lacks_tag",
        value: "museum",
      }),
    ).toBe(true);
  });

  it("evaluates multi-clause conjunctions with AND / OR", () => {
    const andQuery: QueryGroup = {
      id: "g1",
      conjunction: "AND",
      rules: [
        { id: "r1", field: "country", operator: "equals", value: "Japan" },
        { id: "r2", field: "rating", operator: ">=", value: 5 },
      ],
    };

    expect(evaluateQueryTree(testPOIs[0], andQuery)).toBe(true);
    expect(evaluateQueryTree(testPOIs[1], andQuery)).toBe(false);
    const matches = filterPOIsInMemory(testPOIs, andQuery);
    expect(matches).toHaveLength(1);
    expect(matches[0].name).toBe("Senso-ji Temple");

    const orQuery: QueryGroup = {
      id: "g2",
      conjunction: "OR",
      rules: [
        { id: "r1", field: "city", operator: "equals", value: "Kyoto" },
        { id: "r2", field: "city", operator: "equals", value: "Paris" },
      ],
    };

    const orMatches = filterPOIsInMemory(testPOIs, orQuery);
    expect(orMatches).toHaveLength(2);
  });

  it("returns all POIs when query tree is empty", () => {
    expect(filterPOIsInMemory(testPOIs, null)).toHaveLength(3);
    expect(
      filterPOIsInMemory(testPOIs, { id: "g", conjunction: "AND", rules: [] }),
    ).toHaveLength(3);
  });
});
