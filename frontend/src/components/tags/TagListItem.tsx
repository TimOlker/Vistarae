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

import React from "react";
import { Trash2, Tag as TagIcon, Hash } from "lucide-react";

export interface TagItem {
  id: string;
  slug: string;
  name: string;
  aliases: string[];
  poi_count: number;
  created_at?: string;
}

interface TagListItemProps {
  tag: TagItem;
  onDelete: (tag: TagItem) => void;
}

export const TagListItem: React.FC<TagListItemProps> = ({ tag, onDelete }) => {
  return (
    <div
      data-testid={`tag-item-${tag.slug}`}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 16px",
        background: "var(--color-bg-card, #ffffff)",
        borderRadius: "8px",
        border: "1px solid var(--color-border, #e5e7eb)",
        marginBottom: "8px",
        transition: "box-shadow 0.15s ease",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <TagIcon size={16} color="var(--color-primary, #2563eb)" />
          <span style={{ fontWeight: 600, fontSize: "15px", color: "var(--color-text, #111827)" }}>
            {tag.name}
          </span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "2px",
              padding: "2px 8px",
              fontSize: "12px",
              fontWeight: 500,
              background: "var(--color-bg-muted, #f3f4f6)",
              color: "var(--color-text-muted, #4b5563)",
              borderRadius: "4px",
              fontFamily: "monospace",
            }}
          >
            <Hash size={12} />
            {tag.slug}
          </span>
          <span
            data-testid={`tag-poi-count-${tag.slug}`}
            style={{
              fontSize: "12px",
              padding: "2px 8px",
              borderRadius: "12px",
              background: tag.poi_count > 0 ? "rgba(37, 99, 235, 0.1)" : "rgba(107, 114, 128, 0.1)",
              color: tag.poi_count > 0 ? "var(--color-primary, #2563eb)" : "var(--color-text-muted, #6b7280)",
              fontWeight: 600,
            }}
          >
            {tag.poi_count} {tag.poi_count === 1 ? "POI" : "POIs"}
          </span>
        </div>

        {/* Alias Pills */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginLeft: "26px" }}>
          {tag.aliases && tag.aliases.length > 0 ? (
            tag.aliases.map((alias) => (
              <span
                key={alias}
                style={{
                  fontSize: "11px",
                  padding: "1px 6px",
                  borderRadius: "4px",
                  background: "var(--color-bg-subtle, #f9fafb)",
                  border: "1px solid var(--color-border, #e5e7eb)",
                  color: "var(--color-text-muted, #6b7280)",
                }}
              >
                {alias}
              </span>
            ))
          ) : (
            <span style={{ fontSize: "11px", color: "var(--color-text-muted, #9ca3af)", fontStyle: "italic" }}>
              No aliases configured
            </span>
          )}
        </div>
      </div>

      <div>
        <button
          type="button"
          data-testid={`delete-tag-btn-${tag.slug}`}
          onClick={() => onDelete(tag)}
          aria-label={`Delete tag ${tag.name}`}
          style={{
            background: "transparent",
            border: "none",
            color: "var(--color-danger, #ef4444)",
            cursor: "pointer",
            padding: "8px",
            borderRadius: "6px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          title={`Delete ${tag.name}`}
        >
          <Trash2 size={16} />
        </button>
      </div>
    </div>
  );
};
