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

import React, { useState } from "react";
import { Bookmark, Save, Trash2, Copy } from "lucide-react";
import type { FilterRule } from "../../types/filter";

export interface SavedRuleSelectorProps {
  savedRules: FilterRule[];
  activeRuleId: string | null;
  onSelectRule: (rule: FilterRule | null) => void;
  onSaveRule: (name: string, isOverwrite: boolean) => Promise<void>;
  onDeleteRule: (id: string) => Promise<void>;
  disabled?: boolean;
}

export const SavedRuleSelector: React.FC<SavedRuleSelectorProps> = ({
  savedRules,
  activeRuleId,
  onSelectRule,
  onSaveRule,
  onDeleteRule,
  disabled = false,
}) => {
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showOverwriteModal, setShowOverwriteModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [newRuleName, setNewRuleName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const activeRule = savedRules.find((r) => r.id === activeRuleId);

  const handleDropdownChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (!val) {
      onSelectRule(null);
    } else {
      const selected = savedRules.find((r) => r.id === val);
      onSelectRule(selected || null);
    }
  };

  const handleSaveClick = () => {
    if (activeRule) {
      // Overwrite confirmation flow (REQ-MAIN-015)
      setShowOverwriteModal(true);
    } else {
      // Create new rule flow (REQ-MAIN-016)
      setNewRuleName("");
      setShowSaveModal(true);
    }
  };

  const handleSaveAsClick = () => {
    setNewRuleName(activeRule ? `${activeRule.name} (Copy)` : "");
    setShowSaveModal(true);
  };

  const confirmOverwrite = async () => {
    if (!activeRule) return;
    setIsSubmitting(true);
    try {
      await onSaveRule(activeRule.name, true);
      setShowOverwriteModal(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const confirmSaveNew = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newRuleName.trim();
    if (!trimmed) return;
    setIsSubmitting(true);
    try {
      await onSaveRule(trimmed, false);
      setShowSaveModal(false);
      setNewRuleName("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const confirmDelete = async () => {
    if (!activeRuleId) return;
    setIsSubmitting(true);
    try {
      await onDeleteRule(activeRuleId);
      setShowDeleteModal(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="saved-rule-selector"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "8px",
        flexWrap: "wrap",
      }}
    >
      {/* Dropdown Selector */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        <Bookmark size={14} style={{ color: "var(--accent, #2563eb)" }} />
        <select
          aria-label="Saved filter rules"
          data-testid="saved-rule-dropdown"
          value={activeRuleId || ""}
          onChange={handleDropdownChange}
          disabled={disabled}
          style={{
            padding: "4px 10px",
            fontSize: "12px",
            borderRadius: "6px",
            border: "1px solid var(--border-color, #cbd5e1)",
            backgroundColor: "var(--bg-surface, #ffffff)",
            color: "var(--text-primary, #0f172a)",
            fontWeight: activeRuleId ? 600 : 400,
          }}
        >
          <option value="">Custom Filter (Unsaved)</option>
          {savedRules.map((rule) => (
            <option key={rule.id} value={rule.id}>
              {rule.name}
            </option>
          ))}
        </select>
      </div>

      {/* Save Button */}
      <button
        type="button"
        data-testid="save-rule-btn"
        onClick={handleSaveClick}
        disabled={disabled || isSubmitting}
        title={
          activeRule ? `Save changes to ${activeRule.name}` : "Save as new rule"
        }
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
          padding: "4px 8px",
          fontSize: "12px",
          borderRadius: "6px",
          border: "1px solid var(--border-color, #cbd5e1)",
          backgroundColor: "var(--bg-surface, #ffffff)",
          color: "var(--text-primary, #0f172a)",
          cursor: "pointer",
        }}
      >
        <Save size={13} />
        <span>Save Rule</span>
      </button>

      {/* Save As Button (REQ-MAIN-016) */}
      {activeRule && (
        <button
          type="button"
          data-testid="save-as-rule-btn"
          onClick={handleSaveAsClick}
          disabled={disabled || isSubmitting}
          title="Save as a new independent rule"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            padding: "4px 8px",
            fontSize: "12px",
            borderRadius: "6px",
            border: "1px solid var(--border-color, #cbd5e1)",
            backgroundColor: "var(--bg-surface, #ffffff)",
            color: "var(--text-primary, #0f172a)",
            cursor: "pointer",
          }}
        >
          <Copy size={13} />
          <span>Save As...</span>
        </button>
      )}

      {/* Delete Button (REQ-MAIN-018) */}
      {activeRule && (
        <button
          type="button"
          data-testid="delete-rule-btn"
          onClick={() => setShowDeleteModal(true)}
          disabled={disabled || isSubmitting}
          title={`Delete ${activeRule.name}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            padding: "4px 8px",
            fontSize: "12px",
            borderRadius: "6px",
            border: "1px solid var(--danger, #ef4444)",
            backgroundColor: "#fef2f2",
            color: "var(--danger, #ef4444)",
            cursor: "pointer",
          }}
        >
          <Trash2 size={13} />
          <span>Delete</span>
        </button>
      )}

      {/* Save New Modal */}
      {showSaveModal && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <form
            onSubmit={confirmSaveNew}
            style={{
              backgroundColor: "var(--bg-surface, #ffffff)",
              padding: "20px",
              borderRadius: "10px",
              width: "360px",
              boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
              display: "flex",
              flexDirection: "column",
              gap: "14px",
            }}
          >
            <h3 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>
              Save Filter Rule
            </h3>
            <p
              style={{
                fontSize: "13px",
                color: "var(--text-muted)",
                margin: 0,
              }}
            >
              Give this rule a descriptive name to easily recall its query,
              table columns, and pin colors later.
            </p>
            <input
              type="text"
              autoFocus
              data-testid="save-rule-name-input"
              aria-label="Rule name"
              placeholder="e.g. Kyoto 4-Star Gems"
              value={newRuleName}
              onChange={(e) => setNewRuleName(e.target.value)}
              maxLength={100}
              required
              style={{
                padding: "8px 12px",
                borderRadius: "6px",
                border: "1px solid var(--border-color, #cbd5e1)",
                fontSize: "14px",
              }}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "8px",
              }}
            >
              <button
                type="button"
                onClick={() => setShowSaveModal(false)}
                style={{
                  padding: "6px 14px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  background: "transparent",
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                data-testid="confirm-save-rule-btn"
                disabled={!newRuleName.trim() || isSubmitting}
                style={{
                  padding: "6px 14px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor: "var(--accent, #2563eb)",
                  color: "#ffffff",
                  fontWeight: 600,
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                {isSubmitting ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Overwrite Confirmation Modal (REQ-MAIN-015) */}
      {showOverwriteModal && activeRule && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: "var(--bg-surface, #ffffff)",
              padding: "20px",
              borderRadius: "10px",
              width: "360px",
              boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
              display: "flex",
              flexDirection: "column",
              gap: "14px",
            }}
          >
            <h3 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>
              Overwrite Rule?
            </h3>
            <p
              style={{
                fontSize: "13px",
                color: "var(--text-secondary)",
                margin: 0,
              }}
            >
              Are you sure you want to overwrite{" "}
              <strong>&quot;{activeRule.name}&quot;</strong> with the current
              filter query, table column configuration, and pin color scheme?
            </p>
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "8px",
              }}
            >
              <button
                type="button"
                onClick={() => setShowOverwriteModal(false)}
                style={{
                  padding: "6px 14px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  background: "transparent",
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="confirm-overwrite-btn"
                onClick={confirmOverwrite}
                disabled={isSubmitting}
                style={{
                  padding: "6px 14px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor: "var(--accent, #2563eb)",
                  color: "#ffffff",
                  fontWeight: 600,
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                {isSubmitting ? "Overwriting..." : "Overwrite"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal (REQ-MAIN-018) */}
      {showDeleteModal && activeRule && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: "var(--bg-surface, #ffffff)",
              padding: "20px",
              borderRadius: "10px",
              width: "360px",
              boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
              display: "flex",
              flexDirection: "column",
              gap: "14px",
            }}
          >
            <h3
              style={{
                fontSize: "16px",
                fontWeight: 700,
                margin: 0,
                color: "var(--danger, #ef4444)",
              }}
            >
              Delete Rule?
            </h3>
            <p
              style={{
                fontSize: "13px",
                color: "var(--text-secondary)",
                margin: 0,
              }}
            >
              Are you sure you want to permanently delete{" "}
              <strong>&quot;{activeRule.name}&quot;</strong>? This action cannot
              be undone.
            </p>
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "8px",
              }}
            >
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                style={{
                  padding: "6px 14px",
                  borderRadius: "6px",
                  border: "1px solid var(--border-color, #cbd5e1)",
                  background: "transparent",
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="confirm-delete-rule-btn"
                onClick={confirmDelete}
                disabled={isSubmitting}
                style={{
                  padding: "6px 14px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor: "var(--danger, #ef4444)",
                  color: "#ffffff",
                  fontWeight: 600,
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                {isSubmitting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SavedRuleSelector;
