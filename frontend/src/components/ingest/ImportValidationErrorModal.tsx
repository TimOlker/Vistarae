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
import { Modal } from "../common/Modal";
import { AlertTriangle } from "lucide-react";

export interface ValidationIssue {
  row_number: number;
  column: string;
  raw_value: string;
  message: string;
}

export interface ImportValidationErrorModalProps {
  isOpen: boolean;
  issues: ValidationIssue[];
  totalRows: number;
  invalidRowCount: number;
  onSkipAndContinue: () => void;
  onAbort: () => void;
}

export const ImportValidationErrorModal: React.FC<ImportValidationErrorModalProps> = ({
  isOpen,
  issues,
  totalRows,
  invalidRowCount,
  onSkipAndContinue,
  onAbort,
}) => {
  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onAbort} title="Import Validation Issues Detected">
      <div className="space-y-4">
        <div className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-md">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800">
            <span className="font-semibold">
              {invalidRowCount} of {totalRows} rows contain invalid or unparseable data.
            </span>
            <p className="mt-1">
              You can skip these invalid rows and continue staging the valid records, or abort the
              import to correct your file.
            </p>
          </div>
        </div>

        <div className="max-h-72 overflow-y-auto border border-gray-200 rounded-md divide-y divide-gray-100">
          {issues.map((issue, idx) => (
            <div key={idx} className="p-3 text-sm flex flex-col md:flex-row md:items-center justify-between gap-2 hover:bg-gray-50">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs px-2 py-0.5 bg-gray-100 text-gray-700 rounded font-semibold">
                  Row {issue.row_number}
                </span>
                <span className="font-medium text-gray-900">{issue.column}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-600 font-mono bg-red-50 px-2 py-0.5 rounded border border-red-100 truncate max-w-xs">
                  {issue.raw_value || "<empty>"}
                </span>
                <span className="text-xs text-gray-500">{issue.message}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={onAbort}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
          >
            Abort Import
          </button>
          <button
            type="button"
            onClick={onSkipAndContinue}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Skip {invalidRowCount} Invalid Row{invalidRowCount !== 1 ? "s" : ""} & Continue
          </button>
        </div>
      </div>
    </Modal>
  );
};

