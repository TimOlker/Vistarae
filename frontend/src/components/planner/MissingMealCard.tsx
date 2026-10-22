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
import { Utensils, Check, Briefcase } from "lucide-react";
import type { MissingMealAdvisory } from "../../services/itineraryService";

interface MissingMealCardProps {
  advisory: MissingMealAdvisory;
  onPackLunch?: (advisory: MissingMealAdvisory) => void;
}

export const MissingMealCard: React.FC<MissingMealCardProps> = ({
  advisory,
  onPackLunch,
}) => {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const mealLabel =
    advisory.meal_type.charAt(0).toUpperCase() + advisory.meal_type.slice(1);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "10px",
        padding: "10px 12px",
        backgroundColor: "rgba(245, 158, 11, 0.08)",
        border: "1px dashed var(--warning)",
        borderRadius: "var(--radius-md)",
        marginBottom: "12px",
        fontSize: "0.82rem",
      }}
    >
      <div style={{ color: "var(--warning)", marginTop: "2px" }}>
        <Utensils size={16} />
      </div>

      <div style={{ flex: 1 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "2px",
          }}
        >
          <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
            Missing {mealLabel}
            {advisory.gap_start && advisory.gap_end
              ? ` (${advisory.gap_start.slice(0, 5)} - ${advisory.gap_end.slice(
                  0,
                  5,
                )})`
              : ""}
          </span>
          <span
            style={{
              fontSize: "0.68rem",
              color: "var(--warning)",
              fontWeight: 500,
              textTransform: "uppercase",
            }}
          >
            Advisory
          </span>
        </div>

        <p
          style={{
            color: "var(--text-secondary)",
            marginBottom: "8px",
            lineHeight: 1.3,
          }}
        >
          No meal scheduled. Suggestion:{" "}
          <strong>
            {advisory.suggested_poi_title || "Nearby Local Eatery"}
          </strong>
        </p>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {advisory.meal_type === "lunch" ? (
            <button
              type="button"
              onClick={() => {
                onPackLunch?.(advisory);
                setDismissed(true);
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "0.72rem",
                padding: "3px 8px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "var(--bg-card)",
                border: "1px solid var(--border-color)",
                color: "var(--text-secondary)",
                fontWeight: 500,
              }}
              title="Acknowledge by planning to pack lunch"
            >
              <Briefcase size={12} /> Pack Lunch
            </button>
          ) : null}

          <button
            type="button"
            onClick={() => setDismissed(true)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              fontSize: "0.72rem",
              padding: "3px 8px",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "var(--bg-card)",
              border: "1px solid var(--border-color)",
              color: "var(--text-muted)",
            }}
          >
            <Check size={12} /> Dismiss
          </button>
        </div>
      </div>
    </div>
  );
};
