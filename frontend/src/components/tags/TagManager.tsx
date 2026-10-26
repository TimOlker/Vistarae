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

import React, { useState, useEffect, useMemo } from "react";
import { Plus, Search, AlertCircle, ExternalLink, X, ShieldAlert } from "lucide-react";
import { TagListItem, TagItem } from "./TagListItem";
import { apiFetch } from "../../services/api";
import { useToast } from "../../context/ToastContext";

export const TagManager: React.FC = () => {
  const [tags, setTags] = useState<TagItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const { showToast } = useToast();

  // Modals state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [newTagSlug, setNewTagSlug] = useState("");
  const [newTagAliases, setNewTagAliases] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Deletion guard state
  const [tagToDelete, setTagToDelete] = useState<TagItem | null>(null);
  const [conflictModalData, setConflictModalData] = useState<{
    tag: TagItem;
    count: number;
    remediationUrl: string;
  } | null>(null);

  const fetchTags = async () => {
    setIsLoading(true);
    try {
      const data = await apiFetch<TagItem[]>("/api/pois/tags");
      // Sort alphabetically by name
      const sorted = (data || []).sort((a, b) => a.name.localeCompare(b.name));
      setTags(sorted);
    } catch (err: any) {
      showToast(err.message || "Failed to load tags", "error");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTags();
  }, []);

  const filteredTags = useMemo(() => {
    if (!searchQuery.trim()) return tags;
    const q = searchQuery.toLowerCase();
    return tags.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.slug.toLowerCase().includes(q) ||
        t.aliases.some((a) => a.toLowerCase().includes(q)),
    );
  }, [tags, searchQuery]);

  const autoDerivedSlug = useMemo(() => {
    return newTagName
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }, [newTagName]);

  const handleCreateTag = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!newTagName.trim()) {
      setFormError("Tag name is required.");
      return;
    }

    const slug = (newTagSlug.trim() || autoDerivedSlug).toLowerCase();
    const aliases = newTagAliases
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    setIsSubmitting(true);
    try {
      const created = await apiFetch<TagItem>("/api/pois/tags", {
        method: "POST",
        body: JSON.stringify({
          name: newTagName.trim(),
          slug,
          aliases,
        }),
      });
      showToast(`Tag "${created.name}" created!`, "success");
      setIsAddModalOpen(false);
      setNewTagName("");
      setNewTagSlug("");
      setNewTagAliases("");
      fetchTags();
    } catch (err: any) {
      setFormError(err.message || "Failed to create tag. The slug may already exist.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteClick = (tag: TagItem) => {
    if (tag.poi_count > 0) {
      setConflictModalData({
        tag,
        count: tag.poi_count,
        remediationUrl: `/?filter_tag=${tag.slug}`,
      });
    } else {
      setTagToDelete(tag);
    }
  };

  const handleConfirmDelete = async () => {
    if (!tagToDelete) return;
    try {
      await apiFetch(`/api/pois/tags/${tagToDelete.id}`, {
        method: "DELETE",
      });
      showToast(`Tag "${tagToDelete.name}" deleted.`, "success");
      setTagToDelete(null);
      fetchTags();
    } catch (err: any) {
      if (err.status === 409 || err.referencing_poi_count) {
        setConflictModalData({
          tag: tagToDelete,
          count: err.referencing_poi_count || tagToDelete.poi_count,
          remediationUrl: err.remediation_filter_url || `/?filter_tag=${tagToDelete.slug}`,
        });
        setTagToDelete(null);
      } else {
        showToast(err.message || "Failed to delete tag", "error");
      }
    }
  };

  return (
    <div data-testid="tag-manager" style={{ padding: "8px 0" }}>
      {/* Header toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          marginBottom: "20px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ position: "relative", flex: "1 1 240px", maxWidth: "360px" }}>
          <Search
            size={16}
            style={{
              position: "absolute",
              left: "12px",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--color-text-muted, #9ca3af)",
            }}
          />
          <input
            type="text"
            data-testid="tag-search-input"
            placeholder="Search tags, slugs, or aliases..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px 8px 36px",
              borderRadius: "6px",
              border: "1px solid var(--color-border, #d1d5db)",
              fontSize: "14px",
              background: "var(--color-bg, #ffffff)",
              color: "var(--color-text, #111827)",
            }}
          />
        </div>

        <button
          type="button"
          data-testid="add-tag-btn"
          onClick={() => {
            setFormError(null);
            setIsAddModalOpen(true);
          }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 16px",
            background: "var(--color-primary, #2563eb)",
            color: "#ffffff",
            fontWeight: 600,
            fontSize: "14px",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
          }}
        >
          <Plus size={16} />
          Add Tag
        </button>
      </div>

      {/* Tag List */}
      {isLoading ? (
        <div style={{ padding: "40px", textAlign: "center", color: "var(--color-text-muted, #6b7280)" }}>
          Loading tags...
        </div>
      ) : filteredTags.length === 0 ? (
        <div
          data-testid="no-tags-message"
          style={{
            padding: "40px 20px",
            textAlign: "center",
            background: "var(--color-bg-card, #f9fafb)",
            border: "1px dashed var(--color-border, #d1d5db)",
            borderRadius: "8px",
            color: "var(--color-text-muted, #6b7280)",
          }}
        >
          {searchQuery ? `No tags found matching "${searchQuery}".` : "No tags in your library. Add one above!"}
        </div>
      ) : (
        <div data-testid="tag-list">
          {filteredTags.map((tag) => (
            <TagListItem key={tag.id} tag={tag} onDelete={handleDeleteClick} />
          ))}
        </div>
      )}

      {/* Add Tag Modal */}
      {isAddModalOpen && (
        <div
          data-testid="add-tag-modal"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "16px",
          }}
        >
          <div
            style={{
              background: "var(--color-bg-card, #ffffff)",
              borderRadius: "10px",
              padding: "24px",
              maxWidth: "460px",
              width: "100%",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "18px", fontWeight: 700, margin: 0, color: "var(--color-text, #111827)" }}>
                Add New Tag
              </h2>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--color-text-muted, #6b7280)" }}
              >
                <X size={20} />
              </button>
            </div>

            {formError && (
              <div
                data-testid="tag-form-error"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "10px 12px",
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  borderRadius: "6px",
                  color: "#b91c1c",
                  fontSize: "13px",
                  marginBottom: "16px",
                }}
              >
                <AlertCircle size={16} />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateTag}>
              <div style={{ marginBottom: "14px" }}>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>
                  Display Name *
                </label>
                <input
                  type="text"
                  data-testid="new-tag-name-input"
                  required
                  placeholder="e.g. Historic Railway"
                  value={newTagName}
                  onChange={(e) => setNewTagName(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid var(--color-border, #d1d5db)",
                    fontSize: "14px",
                  }}
                />
              </div>

              <div style={{ marginBottom: "14px" }}>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>
                  Slug ID (Immutable)
                </label>
                <input
                  type="text"
                  data-testid="new-tag-slug-input"
                  placeholder={autoDerivedSlug || "e.g. historic_railway"}
                  value={newTagSlug}
                  onChange={(e) => setNewTagSlug(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid var(--color-border, #d1d5db)",
                    fontSize: "14px",
                    fontFamily: "monospace",
                  }}
                />
                <span style={{ fontSize: "11px", color: "var(--color-text-muted, #6b7280)", marginTop: "2px", display: "block" }}>
                  Auto-derived: {autoDerivedSlug || "none"}
                </span>
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>
                  Search Aliases (Comma-separated)
                </label>
                <input
                  type="text"
                  data-testid="new-tag-aliases-input"
                  placeholder="e.g. steam train, cog railway, funicular"
                  value={newTagAliases}
                  onChange={(e) => setNewTagAliases(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid var(--color-border, #d1d5db)",
                    fontSize: "14px",
                  }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  style={{
                    padding: "8px 14px",
                    borderRadius: "6px",
                    border: "1px solid var(--color-border, #d1d5db)",
                    background: "#ffffff",
                    cursor: "pointer",
                    fontSize: "14px",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="submit-create-tag-btn"
                  disabled={isSubmitting}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "6px",
                    border: "none",
                    background: "var(--color-primary, #2563eb)",
                    color: "#ffffff",
                    fontWeight: 600,
                    cursor: "pointer",
                    fontSize: "14px",
                  }}
                >
                  {isSubmitting ? "Creating..." : "Create Tag"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal (poi_count === 0) */}
      {tagToDelete && (
        <div
          data-testid="delete-confirm-modal"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "16px",
          }}
        >
          <div
            style={{
              background: "#ffffff",
              borderRadius: "10px",
              padding: "24px",
              maxWidth: "420px",
              width: "100%",
            }}
          >
            <h3 style={{ fontSize: "16px", fontWeight: 700, margin: "0 0 10px 0" }}>
              Delete Tag "{tagToDelete.name}"?
            </h3>
            <p style={{ fontSize: "14px", color: "var(--color-text-muted, #4b5563)", margin: "0 0 20px 0" }}>
              This tag has no associated POIs and will be permanently removed from your library.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setTagToDelete(null)}
                style={{
                  padding: "8px 14px",
                  borderRadius: "6px",
                  border: "1px solid #d1d5db",
                  background: "#ffffff",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="confirm-delete-tag-btn"
                onClick={handleConfirmDelete}
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "none",
                  background: "#dc2626",
                  color: "#ffffff",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Delete Tag
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deletion Guard Conflict Modal (poi_count > 0) */}
      {conflictModalData && (
        <div
          data-testid="delete-conflict-modal"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "16px",
          }}
        >
          <div
            style={{
              background: "#ffffff",
              borderRadius: "10px",
              padding: "24px",
              maxWidth: "460px",
              width: "100%",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "14px" }}>
              <div
                style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "50%",
                  background: "#fef2f2",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#dc2626",
                }}
              >
                <ShieldAlert size={22} />
              </div>
              <div>
                <h3 style={{ fontSize: "17px", fontWeight: 700, margin: 0, color: "#111827" }}>
                  Cannot Delete Tag in Use
                </h3>
                <span style={{ fontSize: "12px", color: "#6b7280" }}>
                  RFC 7807 Referential Integrity Protection
                </span>
              </div>
            </div>

            <p style={{ fontSize: "14px", color: "#374151", lineHeight: 1.5, margin: "0 0 16px 0" }}>
              Tag <strong>"{conflictModalData.tag.name}"</strong> is currently assigned to{" "}
              <strong>
                {conflictModalData.count} {conflictModalData.count === 1 ? "POI" : "POIs"}
              </strong>
              . You must remove this tag from all referencing POIs before deleting it.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <a
                href={conflictModalData.remediationUrl}
                data-testid="view-affected-pois-btn"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  padding: "10px 16px",
                  borderRadius: "6px",
                  background: "var(--color-primary, #2563eb)",
                  color: "#ffffff",
                  textDecoration: "none",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                }}
              >
                <ExternalLink size={16} />
                View {conflictModalData.count} Affected POIs in Table
              </a>

              <button
                type="button"
                data-testid="close-conflict-modal-btn"
                onClick={() => setConflictModalData(null)}
                style={{
                  padding: "8px 14px",
                  borderRadius: "6px",
                  border: "1px solid #d1d5db",
                  background: "#ffffff",
                  cursor: "pointer",
                  fontSize: "14px",
                  color: "#4b5563",
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
