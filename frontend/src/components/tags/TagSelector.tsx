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
import { Tag as TagIcon, Loader2 } from "lucide-react";
import { apiFetch } from "../../services/api";
import type { TagItem } from "./TagListItem";

export interface TagSelectorProps {
  selectedTags: string[];
  onChange: (tags: string[]) => void;
  availableTags?: TagItem[];
  label?: string;
  helperText?: string;
  maxHeight?: string | number;
}

export const TagSelector: React.FC<TagSelectorProps> = ({
  selectedTags,
  onChange,
  availableTags: initialAvailableTags,
  label = "Tags",
  helperText = "Click to add or remove",
  maxHeight = 125,
}) => {
  const [userTags, setUserTags] = useState<TagItem[]>(
    initialAvailableTags || [],
  );
  const [isLoading, setIsLoading] = useState<boolean>(
    !initialAvailableTags || initialAvailableTags.length === 0,
  );

  useEffect(() => {
    if (initialAvailableTags && initialAvailableTags.length > 0) {
      setUserTags(initialAvailableTags);
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    const fetchTags = async () => {
      setIsLoading(true);
      try {
        const data = await apiFetch<TagItem[]>("/api/pois/tags");
        if (isMounted && Array.isArray(data)) {
          const sorted = data.sort((a, b) => a.name.localeCompare(b.name));
          setUserTags(sorted);
        }
      } catch (err) {
        console.warn("Failed to load user tags for selection", err);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchTags();
    return () => {
      isMounted = false;
    };
  }, [initialAvailableTags]);

  const allDisplayTags = useMemo(() => {
    const list = [...userTags];
    selectedTags.forEach((sTag) => {
      const exists = list.some(
        (t) =>
          t.slug.toLowerCase() === sTag.toLowerCase() ||
          t.name.toLowerCase() === sTag.toLowerCase(),
      );
      if (!exists && sTag.trim()) {
        const rawText = sTag.replace(/_/g, " ");
        const formattedName =
          rawText.charAt(0).toUpperCase() + rawText.slice(1);
        list.push({
          id: sTag,
          slug: sTag,
          name: formattedName,
          aliases: [],
          poi_count: 0,
        });
      }
    });
    return list;
  }, [userTags, selectedTags]);

  const handleToggleTag = (tag: TagItem) => {
    const isSelected = selectedTags.some(
      (t) =>
        t.toLowerCase() === tag.slug.toLowerCase() ||
        (tag.name && t.toLowerCase() === tag.name.toLowerCase()),
    );

    if (isSelected) {
      const next = selectedTags.filter(
        (t) =>
          t.toLowerCase() !== tag.slug.toLowerCase() &&
          (!tag.name || t.toLowerCase() !== tag.name.toLowerCase()),
      );
      onChange(next);
    } else {
      onChange([...selectedTags, tag.slug]);
    }
  };

  return (
    <div id="vistarae-tags-container" data-testid="vistarae-tags-container">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: "6px",
        }}
      >
        <label
          style={{
            fontSize: "12px",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            gap: "6px",
            color: "var(--text-secondary, #475569)",
          }}
        >
          <TagIcon size={14} style={{ color: "var(--accent, #2563eb)" }} />
          {label} {selectedTags.length > 0 ? `(${selectedTags.length})` : ""}
        </label>
        <span
          className="vistarae-text-muted"
          style={{
            fontSize: "0.75rem",
            color: "var(--text-muted, #94a3b8)",
          }}
        >
          {helperText}
        </span>
      </div>

      <div
        id="vistarae-tag-pills"
        className="vistarae-tag-pills"
        data-testid="vistarae-tag-pills"
        style={{ maxHeight }}
      >
        {isLoading && userTags.length === 0 ? (
          <span
            className="vistarae-text-muted"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "0.825rem",
              color: "var(--text-muted, #94a3b8)",
            }}
          >
            <Loader2 size={13} className="animate-spin" />
            Loading your configured tags...
          </span>
        ) : allDisplayTags.length === 0 ? (
          <span
            className="vistarae-text-muted"
            style={{
              fontSize: "0.825rem",
              color: "var(--text-muted, #94a3b8)",
              fontStyle: "italic",
            }}
          >
            No configured tags found in your Vistarae library.
          </span>
        ) : (
          allDisplayTags.map((tag) => {
            const isSelected = selectedTags.some(
              (t) =>
                t.toLowerCase() === tag.slug.toLowerCase() ||
                (tag.name && t.toLowerCase() === tag.name.toLowerCase()),
            );
            const rawText = tag.name || tag.slug.replace(/_/g, " ");
            const formattedName =
              rawText.charAt(0).toUpperCase() + rawText.slice(1);

            return (
              <button
                key={tag.slug}
                type="button"
                className={`vistarae-tag-pill ${isSelected ? "active" : ""}`}
                data-testid={`tag-pill-${tag.slug}`}
                aria-pressed={isSelected}
                onClick={() => handleToggleTag(tag)}
              >
                {isSelected ? `✓ ${formattedName}` : formattedName}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};

