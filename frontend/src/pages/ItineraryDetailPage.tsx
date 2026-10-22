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

/**
 * ItineraryDetailPage component (T031, REQ-PLAN-001, REQ-PLAN-015, REQ-PLAN-016).
 * Deep-linkable detail page for /trips/:id with tabbed views:
 *  - Workbench (drag-and-drop timeline)
 *  - Route Map (macro and daily leg visualization)
 *  - Print / Export (vector-ready printable view)
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  Calendar,
  MapPin,
  DollarSign,
  ArrowLeft,
  Columns,
  Map as MapIcon,
  Printer,
  Loader2,
  AlertCircle,
} from "lucide-react";
import {
  itineraryService,
  type ItineraryResponse,
  type ItineraryItemResponse,
} from "../services/itineraryService";
import { ItineraryBoard } from "../components/planner/ItineraryBoard";
import { RouteMap } from "../components/planner/RouteMap";
import { PrintExportView } from "../components/planner/PrintExportView";
import { useToast } from "../context/ToastContext";

interface ItineraryDetailPageProps {
  itineraryId: string;
  onNavigateBack: () => void;
}

export const ItineraryDetailPage: React.FC<ItineraryDetailPageProps> = ({
  itineraryId,
  onNavigateBack,
}) => {
  const { showToast } = useToast();
  const [itinerary, setItinerary] = useState<ItineraryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"board" | "map" | "export">(
    "board",
  );

  const loadItinerary = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await itineraryService.getItinerary(itineraryId);
      setItinerary(data);
    } catch (err: unknown) {
      console.error("Failed to load itinerary:", err);
      const msg =
        err instanceof Error ? err.message : "Failed to load itinerary.";
      setError(msg);
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  }, [itineraryId, showToast]);

  useEffect(() => {
    loadItinerary();
  }, [loadItinerary]);

  const handleImportPoi = async (item: ItineraryItemResponse) => {
    try {
      await itineraryService.importPoiToSaved({
        name: item.title,
        lat: item.latitude ?? (item as any).lat ?? 0,
        lng: item.longitude ?? (item as any).lng ?? 0,
        description: item.notes,
        category: item.category,
        estimated_cost: item.cost_cents,
      });
      showToast(`Imported "${item.title}" to your saved POIs!`, "success");
      // Refetch itinerary so item link is updated
      loadItinerary();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to import POI.";
      showToast(msg, "error");
      throw err;
    }
  };

  const formatCost = (cents: number | null | undefined): string => {
    if (!cents || cents <= 0) return "Free";
    return `$${(cents / 100).toFixed(2)}`;
  };

  if (loading) {
    return (
      <div
        data-testid="itinerary-detail-loading"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          color: "var(--text-muted, #94a3b8)",
          gap: "12px",
        }}
      >
        <Loader2 size={24} className="animate-spin" />
        <span>Loading itinerary workbench...</span>
      </div>
    );
  }

  if (error || !itinerary) {
    return (
      <div
        style={{
          maxWidth: "600px",
          margin: "80px auto",
          padding: "32px",
          textAlign: "center",
          background: "var(--bg-surface, #ffffff)",
          borderRadius: "var(--radius-lg, 12px)",
          border: "1px solid var(--border-color, #e2e8f0)",
        }}
      >
        <AlertCircle
          size={36}
          color="var(--danger, #ef4444)"
          style={{ margin: "0 auto 16px" }}
        />
        <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px" }}>
          Itinerary Not Found
        </h2>
        <p
          style={{
            color: "var(--text-secondary, #475569)",
            fontSize: "14px",
            marginBottom: "24px",
          }}
        >
          {error ||
            "The requested itinerary could not be located or you lack access permissions."}
        </p>
        <button
          type="button"
          onClick={onNavigateBack}
          style={{
            padding: "8px 16px",
            borderRadius: "6px",
            background: "var(--accent, #2563eb)",
            color: "#ffffff",
            fontSize: "14px",
            fontWeight: 600,
          }}
        >
          Return to All Trips
        </button>
      </div>
    );
  }

  // If in full print export view
  if (activeTab === "export") {
    return (
      <PrintExportView
        itinerary={itinerary}
        onClose={() => setActiveTab("board")}
      />
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 60px)",
        overflow: "hidden",
        background: "var(--bg-primary, #f8fafc)",
      }}
    >
      {/* Top Details & Navigation Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 24px",
          background: "var(--bg-surface, #ffffff)",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
          zIndex: 20,
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button
            type="button"
            data-testid="back-to-trips-btn"
            onClick={onNavigateBack}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 10px",
              borderRadius: "6px",
              background: "var(--bg-hover, #f1f5f9)",
              color: "var(--text-secondary, #475569)",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            <ArrowLeft size={14} />
            <span>Trips</span>
          </button>

          <div>
            <h1
              data-testid="itinerary-title"
              style={{
                fontSize: "18px",
                fontWeight: 800,
                color: "var(--text-primary, #0f172a)",
                letterSpacing: "-0.01em",
              }}
            >
              {itinerary.title}
            </h1>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                fontSize: "12px",
                color: "var(--text-secondary, #475569)",
                marginTop: "2px",
              }}
            >
              <span
                style={{ display: "flex", alignItems: "center", gap: "4px" }}
              >
                <MapPin size={12} color="var(--accent, #2563eb)" />
                {itinerary.destination}
              </span>
              <span
                style={{ display: "flex", alignItems: "center", gap: "4px" }}
              >
                <Calendar size={12} color="var(--accent, #2563eb)" />
                {itinerary.start_date} &ndash; {itinerary.end_date}
              </span>
              {itinerary.budget_cents ? (
                <span
                  style={{ display: "flex", alignItems: "center", gap: "4px" }}
                >
                  <DollarSign size={12} color="var(--accent, #2563eb)" />
                  Budget: {formatCost(itinerary.budget_cents)} (Est:{" "}
                  {formatCost(itinerary.total_estimated_cost_cents)})
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* View Switcher Tabs & Print Shortcut */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "var(--bg-hover, #f1f5f9)",
              padding: "3px",
              borderRadius: "8px",
              gap: "2px",
            }}
          >
            <button
              type="button"
              data-testid="tab-workbench"
              onClick={() => setActiveTab("board")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                background:
                  activeTab === "board"
                    ? "var(--bg-surface, #ffffff)"
                    : "transparent",
                color:
                  activeTab === "board"
                    ? "var(--accent, #2563eb)"
                    : "var(--text-secondary, #475569)",
                boxShadow:
                  activeTab === "board" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              }}
            >
              <Columns size={14} />
              <span>Workbench</span>
            </button>

            <button
              type="button"
              data-testid="tab-map"
              onClick={() => setActiveTab("map")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                background:
                  activeTab === "map"
                    ? "var(--bg-surface, #ffffff)"
                    : "transparent",
                color:
                  activeTab === "map"
                    ? "var(--accent, #2563eb)"
                    : "var(--text-secondary, #475569)",
                boxShadow:
                  activeTab === "map" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              }}
            >
              <MapIcon size={14} />
              <span>Route Map</span>
            </button>
          </div>

          <button
            type="button"
            data-testid="tab-export"
            onClick={() => setActiveTab("export")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 14px",
              borderRadius: "6px",
              background: "var(--accent-light, #eff6ff)",
              color: "var(--accent, #2563eb)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
              border: "1px solid rgba(37,99,235,0.2)",
            }}
          >
            <Printer size={14} />
            <span>Print PDF</span>
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div
        style={{
          flex: 1,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {activeTab === "board" && (
          <ItineraryBoard
            itinerary={itinerary}
            onUpdateItinerary={setItinerary}
            onImportPoi={handleImportPoi}
          />
        )}

        {activeTab === "map" && (
          <div style={{ flex: 1, padding: "16px", height: "100%" }}>
            <RouteMap itinerary={itinerary} />
          </div>
        )}
      </div>
    </div>
  );
};
