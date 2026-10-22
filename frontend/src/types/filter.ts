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
 * Filter Rules and Visual Query Builder TypeScript types (T-018 / REQ-MAIN-008, REQ-MAIN-012).
 */

export interface RuleClause {
  id: string;
  field: string;
  operator: string;
  value: any;
}

export interface QueryGroup {
  id: string;
  conjunction: "AND" | "OR";
  rules: (RuleClause | QueryGroup)[];
}

export type SortDirection = "asc" | "desc" | "unsorted";

export interface TableConfig {
  visible_columns: string[];
  column_order: string[];
  sort: {
    column: string;
    direction: SortDirection;
  };
}

export type PinColorMode = "uniform" | "rating" | "visit_status" | "custom";

export interface PinColorScheme {
  mode: PinColorMode;
  default_color: string;
  palette: Record<string, string>;
  rule_mappings: Array<{
    field: string;
    operator: string;
    value: any;
    color: string;
  }>;
}

export interface FilterRule {
  id: string;
  user_id: string;
  name: string;
  query_tree: QueryGroup;
  table_config: TableConfig;
  pin_color_scheme: PinColorScheme;
  created_at: string;
  updated_at: string;
}

export interface FilterRuleCreateRequest {
  name: string;
  query_tree: QueryGroup;
  table_config: TableConfig;
  pin_color_scheme: PinColorScheme;
}

export interface FilterRuleUpdateRequest {
  name: string;
  query_tree: QueryGroup;
  table_config: TableConfig;
  pin_color_scheme: PinColorScheme;
}

export interface FilterRuleListResponse {
  items: FilterRule[];
  total: number;
}
