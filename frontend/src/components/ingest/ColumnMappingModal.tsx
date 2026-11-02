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

import React, { useState } from "react";
import { Modal } from "../common/Modal";
import { ArrowRight } from "lucide-react";

export interface ColumnSample {
  column: string;
  sample_values: string[];
}

export interface ColumnMappingModalProps {
  isOpen: boolean;
  unmappedColumns: string[];
  sampleRows: ColumnSample[];
  targetFields: string[];
  onConfirm: (mappings: Record<string, string>) => void;
  onCancel: () => void;
}

export const ColumnMappingModal: React.FC<ColumnMappingModalProps> = ({
  isOpen,
  unmappedColumns,
  sampleRows,
  targetFields,
  onConfirm,
  onCancel,
}) => {
  const [mappings, setMappings] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const col of unmappedColumns) {
      initial[col] = "[Ignore]";
    }
    return initial;
  });

  if (!isOpen) return null;

  const handleSelectChange = (column: string, value: string) => {
    setMappings((prev) => ({
      ...prev,
      [column]: value,
    }));
  };

  const sampleMap = new Map<string, string[]>();
  for (const item of sampleRows) {
    sampleMap.set(item.column, item.sample_values);
  }

  return (
    <Modal isOpen={isOpen} onClose={onCancel} title="Align Unmapped Columns">
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          We found columns that did not automatically match our standard schema. Review the sample
          data below and choose the matching target field or select <code>[Ignore]</code> to skip.
        </p>

        <div className="max-h-96 overflow-y-auto border border-gray-200 rounded-md divide-y divide-gray-200">
          {unmappedColumns.map((col) => {
            const samples = sampleMap.get(col) || [];
            return (
              <div key={col} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <span className="font-semibold text-gray-900 block truncate">{col}</span>
                  <span className="text-xs text-gray-500 block truncate mt-0.5">
                    {samples.join(", ")}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <ArrowRight className="w-4 h-4 text-gray-400 hidden md:block" />
                  <label htmlFor={`map-column-${col}`} className="sr-only">
                    Map {col}
                  </label>
                  <select
                    id={`map-column-${col}`}
                    aria-label={`Map ${col}`}
                    className="border border-gray-300 rounded px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={mappings[col] || "[Ignore]"}
                    onChange={(e) => handleSelectChange(col, e.target.value)}
                  >
                    <option value="[Ignore]">[Ignore]</option>
                    {targetFields.map((field) => (
                      <option key={field} value={field}>
                        {field}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(mappings)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Apply Column Mappings
          </button>
        </div>
      </div>
    </Modal>
  );
};

