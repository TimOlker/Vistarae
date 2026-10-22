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

import type { QueryGroup, RuleClause } from "../types/filter";
import type { POIMapFeature } from "../types/map";

/**
 * Evaluates a single leaf RuleClause against a POI feature in-memory.
 */
export function evaluateRuleClause(
  poi: POIMapFeature,
  clause: RuleClause,
): boolean {
  const { field, operator, value } = clause;
  const op = (operator || "").toLowerCase();

  switch (field) {
    case "city": {
      const city = (poi.city || "").trim();
      const target = String(value ?? "")
        .trim()
        .toLowerCase();
      if (op === "equals" || op === "=") return city.toLowerCase() === target;
      if (op === "not_equals" || op === "!=")
        return city.toLowerCase() !== target;
      if (op === "contains") return city.toLowerCase().includes(target);
      if (op === "is_empty") return city.length === 0;
      if (op === "is_not_empty") return city.length > 0;
      return true;
    }

    case "state_province":
    case "state": {
      const state = (poi.state || "").trim().toLowerCase();
      const target = String(value ?? "")
        .trim()
        .toLowerCase();
      if (op === "equals" || op === "=") return state === target;
      if (op === "not_equals" || op === "!=") return state !== target;
      if (op === "contains") return state.includes(target);
      if (op === "is_empty") return state.length === 0;
      if (op === "is_not_empty") return state.length > 0;
      return true;
    }

    case "country": {
      const country = (poi.country || "").trim().toLowerCase();
      const target = String(value ?? "")
        .trim()
        .toLowerCase();
      if (op === "equals" || op === "=") return country === target;
      if (op === "not_equals" || op === "!=") return country !== target;
      return true;
    }

    case "has_parent": {
      const isParentExpected = Boolean(value);
      const hasParent = Boolean(poi.parent_poi_id);
      return hasParent === isParentExpected;
    }

    case "visit_pending": {
      const expected = Boolean(value);
      return Boolean(poi.visit_pending) === expected;
    }

    case "already_visited": {
      const expected = Boolean(value);
      const visited = Boolean(
        poi.already_visited ||
          poi.visit_state === "visited_return" ||
          poi.visit_state === "visited_do_not_return",
      );
      return visited === expected;
    }

    case "rating": {
      const targetNum = Number(value);
      if (Number.isNaN(targetNum)) return true;
      const r = poi.rating ?? 0;
      if (op === "equals" || op === "=") return poi.rating === targetNum;
      if (op === "not_equals" || op === "!=") return poi.rating !== targetNum;
      if (op === "greater_than" || op === ">") return r > targetNum;
      if (op === "less_than" || op === "<") return r < targetNum;
      if (op === "greater_than_or_equal" || op === ">=") return r >= targetNum;
      if (op === "less_than_or_equal" || op === "<=") return r <= targetNum;
      return true;
    }

    case "list_id": {
      const targetListId = String(value ?? "");
      const listIds: string[] = (poi as any).list_ids || [];
      const hasList =
        listIds.includes(targetListId) || (poi as any).list_id === targetListId;
      if (op === "in_list" || op === "in") return hasList;
      if (op === "not_in_list" || op === "not_in") return !hasList;
      return true;
    }

    case "visit_state": {
      const target = String(value ?? "");
      if (op === "equals" || op === "=") return poi.visit_state === target;
      if (op === "not_equals" || op === "!=") return poi.visit_state !== target;
      return true;
    }

    case "tag":
    case "tags": {
      const targetTag = String(value ?? "")
        .trim()
        .toLowerCase();
      const tags = (poi.tags || []).map((t) =>
        (typeof t === "string" ? t : (t as any).name || "").toLowerCase(),
      );
      const hasTag = tags.includes(targetTag);
      if (op === "has_tag" || op === "contains") return hasTag;
      if (op === "lacks_tag") return !hasTag;
      return true;
    }

    default:
      return true;
  }
}

/**
 * Recursively evaluates a QueryGroup AST against a POI in-memory (T-019).
 */
export function evaluateQueryTree(
  poi: POIMapFeature,
  tree: QueryGroup | null | undefined,
): boolean {
  if (!tree || !tree.rules || tree.rules.length === 0) {
    return true;
  }

  const isAnd = tree.conjunction !== "OR";

  for (const node of tree.rules) {
    let matches = false;
    if ("conjunction" in node) {
      matches = evaluateQueryTree(poi, node as QueryGroup);
    } else {
      matches = evaluateRuleClause(poi, node as RuleClause);
    }

    if (isAnd && !matches) {
      return false; // Short-circuit AND
    }
    if (!isAnd && matches) {
      return true; // Short-circuit OR
    }
  }

  return isAnd;
}

/**
 * In-memory filter evaluating all POIs in a collection against a query tree.
 * Used for instant reactivity when total POIs < 1,000 (REQ-MAIN-010, SC-002).
 */
export function filterPOIsInMemory(
  pois: POIMapFeature[],
  tree: QueryGroup | null | undefined,
): POIMapFeature[] {
  if (!tree || !tree.rules || tree.rules.length === 0) {
    return pois;
  }
  return pois.filter((poi) => evaluateQueryTree(poi, tree));
}
