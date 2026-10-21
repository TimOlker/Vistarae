-- Copyright (c) 2026 Tim Olker
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.
--
-- SPDX-License-Identifier: Apache-2.0

-- Migration: 20261011_add_scanned_paths_conflicts.sql
-- Adds multi-POI conflict tracking to scanned_paths so folders in use by multiple POIs can be flagged and manually refactored.

ALTER TABLE scanned_paths ADD COLUMN IF NOT EXISTS conflict_poi_ids UUID[] DEFAULT '{}';
ALTER TABLE scanned_paths ADD COLUMN IF NOT EXISTS has_conflict BOOLEAN DEFAULT FALSE;
ALTER TABLE scanned_paths ADD COLUMN IF NOT EXISTS conflict_note TEXT;

CREATE INDEX IF NOT EXISTS idx_scanned_paths_conflict ON scanned_paths(has_conflict) WHERE has_conflict = TRUE;
CREATE INDEX IF NOT EXISTS idx_scanned_paths_conflict_poi_ids ON scanned_paths USING GIN(conflict_poi_ids);
