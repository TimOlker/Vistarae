/*
 * Copyright (c) 2026 Tim Olker
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { Calendar } from "lucide-react";

export type DateAddedPreset =
  | "ALL_TIME"
  | "TODAY"
  | "LAST_7_DAYS"
  | "LAST_30_DAYS"
  | "CUSTOM";

export interface DateAddedFilter {
  preset: DateAddedPreset;
  startDate?: string;
  endDate?: string;
}

export interface POIFilterBarProps {
  dateAddedFilter?: DateAddedFilter;
  onDateAddedChange: (filter: DateAddedFilter) => void;
  children?: React.ReactNode;
}

export const POIFilterBar: React.FC<POIFilterBarProps> = ({
  dateAddedFilter = { preset: "ALL_TIME" },
  onDateAddedChange,
  children,
}) => {
  const handlePresetChange = (preset: DateAddedPreset) => {
    if (preset === "CUSTOM") {
      onDateAddedChange({
        preset,
        startDate: dateAddedFilter.startDate || "",
        endDate: dateAddedFilter.endDate || "",
      });
    } else {
      onDateAddedChange({ preset });
    }
  };

  const handleStartDateChange = (startDate: string) => {
    onDateAddedChange({
      ...dateAddedFilter,
      preset: "CUSTOM",
      startDate,
    });
  };

  const handleEndDateChange = (endDate: string) => {
    onDateAddedChange({
      ...dateAddedFilter,
      preset: "CUSTOM",
      endDate,
    });
  };

  return (
    <div
      data-testid="poi-filter-bar"
      className="flex flex-wrap items-center gap-4 p-3 bg-white border-b border-gray-200 text-sm"
    >
      <div className="flex items-center gap-2">
        <Calendar className="w-4 h-4 text-gray-500" />
        <label htmlFor="date-added-select" className="font-medium text-gray-700">
          Date Added:
        </label>
        <select
          id="date-added-select"
          aria-label="Date Added"
          value={dateAddedFilter.preset}
          onChange={(e) => handlePresetChange(e.target.value as DateAddedPreset)}
          className="border border-gray-300 rounded px-2.5 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="ALL_TIME">All Time</option>
          <option value="TODAY">Today</option>
          <option value="LAST_7_DAYS">Last 7 Days</option>
          <option value="LAST_30_DAYS">Last 30 Days</option>
          <option value="CUSTOM">Custom Range</option>
        </select>
      </div>

      {dateAddedFilter.preset === "CUSTOM" && (
        <div className="flex items-center gap-2">
          <label htmlFor="date-added-start" className="sr-only">
            Start Date
          </label>
          <input
            id="date-added-start"
            aria-label="Start Date"
            type="date"
            value={dateAddedFilter.startDate || ""}
            onChange={(e) => handleStartDateChange(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          />
          <span className="text-gray-400">to</span>
          <label htmlFor="date-added-end" className="sr-only">
            End Date
          </label>
          <input
            id="date-added-end"
            aria-label="End Date"
            type="date"
            value={dateAddedFilter.endDate || ""}
            onChange={(e) => handleEndDateChange(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </div>
      )}

      {children}
    </div>
  );
};

