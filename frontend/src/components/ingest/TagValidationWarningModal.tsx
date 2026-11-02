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
import { Tag, AlertCircle } from "lucide-react";

export interface TagValidationWarningModalProps {
  isOpen: boolean;
  unapprovedTags: Record<string, number>;
  onApproveAll: () => void;
  onStripUnapproved: () => void;
  onAbort: () => void;
}

export const TagValidationWarningModal: React.FC<TagValidationWarningModalProps> = ({
  isOpen,
  unapprovedTags,
  onApproveAll,
  onStripUnapproved,
  onAbort,
}) => {
  if (!isOpen) return null;

  const entries = Object.entries(unapprovedTags);
  const tagCount = entries.length;

  return (
    <Modal isOpen={isOpen} onClose={onAbort} title="Unapproved Tags Detected">
      <div className="space-y-4">
        <div className="flex items-start gap-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
          <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <span className="font-semibold">
              Found {tagCount} tag{tagCount !== 1 ? "s" : ""} not in your library.
            </span>
            <p className="mt-1">
              You can approve and add all of these tags directly to your active Tag Library,
              strip unapproved tags and keep only existing ones, or abort the import.
            </p>
          </div>
        </div>

        <div className="p-3 border border-gray-200 rounded-md bg-gray-50 max-h-48 overflow-y-auto flex flex-wrap gap-2">
          {entries.map(([tag, count]) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white border border-gray-300 text-gray-800 shadow-sm"
            >
              <Tag className="w-3 h-3 text-gray-500" />
              {tag} ({count})
            </span>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row justify-end gap-2 pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={onAbort}
            className="px-3 py-2 border border-gray-300 rounded-md text-xs font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
          >
            Abort Import
          </button>
          <button
            type="button"
            onClick={onStripUnapproved}
            className="px-3 py-2 border border-blue-300 bg-white text-blue-700 rounded-md text-xs font-medium hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Strip Unapproved Tags
          </button>
          <button
            type="button"
            onClick={onApproveAll}
            className="px-3 py-2 bg-blue-600 text-white rounded-md text-xs font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Approve & Add All to Library
          </button>
        </div>
      </div>
    </Modal>
  );
};

