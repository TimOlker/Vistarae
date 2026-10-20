// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState } from "react";
import { usePreferences } from "../context/PreferencesContext";
import { useToast } from "../context/ToastContext";
import { Palette, Map, Calendar, Save } from "lucide-react";

export type SettingsTab = "account" | "poi" | "planner";

export const SettingsPage: React.FC<{ initialTab?: SettingsTab }> = ({
  initialTab = "account",
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);
  const { ui, poi, planner, updateUI, updatePOI, updatePlanner } =
    usePreferences();
  const { showToast } = useToast();

  const [saving, setSaving] = useState(false);

  // Local form states
  const [uiForm, setUiForm] = useState(ui);
  const [poiForm, setPoiForm] = useState(poi);
  const [plannerForm, setPlannerForm] = useState(planner);

  const handleSaveUI = async () => {
    setSaving(true);
    try {
      await updateUI(uiForm);
      showToast("Account & UI preferences saved!", "success");
    } catch {
      showToast("Failed to save UI preferences", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleSavePOI = async () => {
    setSaving(true);
    try {
      await updatePOI(poiForm);
      showToast("POI Mode preferences saved!", "success");
    } catch {
      showToast("Failed to save POI preferences", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleSavePlanner = async () => {
    setSaving(true);
    try {
      await updatePlanner(plannerForm);
      showToast("Planner Mode preferences saved!", "success");
    } catch {
      showToast("Failed to save Planner preferences", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "32px 16px" }}>
      <h1 style={{ fontSize: "24px", fontWeight: 800, marginBottom: "20px" }}>
        Preferences
      </h1>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
          marginBottom: "24px",
        }}
      >
        <button
          type="button"
          onClick={() => setActiveTab("account")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 16px",
            borderBottom:
              activeTab === "account"
                ? "2px solid var(--accent, #2563eb)"
                : "2px solid transparent",
            color:
              activeTab === "account"
                ? "var(--accent, #2563eb)"
                : "var(--text-secondary, #64748b)",
            fontWeight: 600,
            fontSize: "14px",
          }}
        >
          <Palette size={16} />
          <span>Account & UI</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("poi")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 16px",
            borderBottom:
              activeTab === "poi"
                ? "2px solid var(--accent, #2563eb)"
                : "2px solid transparent",
            color:
              activeTab === "poi"
                ? "var(--accent, #2563eb)"
                : "var(--text-secondary, #64748b)",
            fontWeight: 600,
            fontSize: "14px",
          }}
        >
          <Map size={16} />
          <span>POI Mode</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("planner")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 16px",
            borderBottom:
              activeTab === "planner"
                ? "2px solid var(--accent, #2563eb)"
                : "2px solid transparent",
            color:
              activeTab === "planner"
                ? "var(--accent, #2563eb)"
                : "var(--text-secondary, #64748b)",
            fontWeight: 600,
            fontSize: "14px",
          }}
        >
          <Calendar size={16} />
          <span>Planner Mode</span>
        </button>
      </div>

      {/* Account & UI Tab */}
      {activeTab === "account" && (
        <div
          className="slide-up"
          style={{
            background: "var(--bg-surface, #ffffff)",
            borderRadius: "var(--radius-lg, 16px)",
            border: "1px solid var(--border-color, #e2e8f0)",
            padding: "28px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          <div>
            <label
              style={{
                fontSize: "13px",
                fontWeight: 700,
                display: "block",
                marginBottom: "8px",
              }}
            >
              Interface Theme
            </label>
            <select
              value={uiForm.theme}
              onChange={(e) =>
                setUiForm((prev) => ({
                  ...prev,
                  theme: e.target.value as "light" | "dark" | "system",
                }))
              }
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-surface)",
                color: "var(--text-primary)",
                fontSize: "13px",
              }}
            >
              <option value="light">Light Mode</option>
              <option value="dark">Dark Mode</option>
              <option value="system">System (OS Preference)</option>
            </select>
          </div>

          <div>
            <label
              style={{
                fontSize: "13px",
                fontWeight: 700,
                display: "block",
                marginBottom: "8px",
              }}
            >
              Notifications
            </label>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                fontSize: "13px",
              }}
            >
              <label
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <input
                  type="checkbox"
                  checked={uiForm.email_notifications}
                  onChange={(e) =>
                    setUiForm((prev) => ({
                      ...prev,
                      email_notifications: e.target.checked,
                    }))
                  }
                />
                <span>
                  Email Notifications (Ingestion completion, weekly digest)
                </span>
              </label>
              <label
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                <input
                  type="checkbox"
                  checked={uiForm.push_notifications}
                  onChange={(e) =>
                    setUiForm((prev) => ({
                      ...prev,
                      push_notifications: e.target.checked,
                    }))
                  }
                />
                <span>
                  Push Notifications (Trip reminders, location alerts)
                </span>
              </label>
            </div>
          </div>

          <button
            type="button"
            onClick={handleSaveUI}
            disabled={saving}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              alignSelf: "flex-start",
              padding: "10px 20px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            <Save size={15} />
            <span>{saving ? "Saving..." : "Save Account Settings"}</span>
          </button>
        </div>
      )}

      {/* POI Mode Tab */}
      {activeTab === "poi" && (
        <div
          className="slide-up"
          style={{
            background: "var(--bg-surface, #ffffff)",
            borderRadius: "var(--radius-lg, 16px)",
            border: "1px solid var(--border-color, #e2e8f0)",
            padding: "28px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          <div>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "14px",
                fontWeight: 700,
              }}
            >
              <input
                type="checkbox"
                checked={poiForm.clustering_enabled}
                onChange={(e) =>
                  setPoiForm((prev) => ({
                    ...prev,
                    clustering_enabled: e.target.checked,
                  }))
                }
              />
              <span>Enable Geospatial Marker Clustering</span>
            </label>
            <p
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginTop: "4px",
                marginLeft: "22px",
              }}
            >
              Groups nearby POIs into count clusters at low zoom levels for 60
              FPS performance
            </p>
          </div>

          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "6px",
              }}
            >
              <label style={{ fontSize: "13px", fontWeight: 700 }}>
                Clustering Radius: {poiForm.clustering_radius_meters}m
              </label>
            </div>
            <input
              type="range"
              min={10}
              max={500}
              value={poiForm.clustering_radius_meters}
              onChange={(e) =>
                setPoiForm((prev) => ({
                  ...prev,
                  clustering_radius_meters: parseInt(e.target.value, 10),
                }))
              }
              style={{ width: "100%" }}
            />
          </div>

          <div>
            <label
              style={{
                fontSize: "13px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Default Map Tile Layer
            </label>
            <select
              value={poiForm.default_map_layer}
              onChange={(e) =>
                setPoiForm((prev) => ({
                  ...prev,
                  default_map_layer: e.target.value,
                }))
              }
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-surface)",
                color: "var(--text-primary)",
                fontSize: "13px",
              }}
            >
              <option value="osm">OpenStreetMap</option>
              <option value="satellite">Satellite (Esri)</option>
              <option value="road">Road (CartoDB)</option>
              <option value="google-roadmap">Google Maps</option>
              <option value="google-hybrid">Google Hybrid</option>
              <option value="amap">AutoNavi / Amap (GCJ-02)</option>
              <option value="baidu">Baidu Maps (BD-09)</option>
            </select>
          </div>

          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "6px",
              }}
            >
              <label style={{ fontSize: "13px", fontWeight: 700 }}>
                Geoproximity Scope: {poiForm.geoproximity_scope_km.toFixed(1)}{" "}
                km
              </label>
            </div>
            <input
              type="range"
              min={1.0}
              max={500.0}
              step={0.5}
              value={poiForm.geoproximity_scope_km}
              onChange={(e) =>
                setPoiForm((prev) => ({
                  ...prev,
                  geoproximity_scope_km: parseFloat(e.target.value),
                }))
              }
              style={{ width: "100%" }}
            />
          </div>

          <button
            type="button"
            onClick={handleSavePOI}
            disabled={saving}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              alignSelf: "flex-start",
              padding: "10px 20px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            <Save size={15} />
            <span>{saving ? "Saving..." : "Save POI Settings"}</span>
          </button>
        </div>
      )}

      {/* Planner Mode Tab */}
      {activeTab === "planner" && (
        <div
          className="slide-up"
          style={{
            background: "var(--bg-surface, #ffffff)",
            borderRadius: "var(--radius-lg, 16px)",
            border: "1px solid var(--border-color, #e2e8f0)",
            padding: "28px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          <div>
            <label
              style={{
                fontSize: "13px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Trip Pacing Mode
            </label>
            <select
              value={plannerForm.pacing_mode}
              onChange={(e) =>
                setPlannerForm((prev) => ({
                  ...prev,
                  pacing_mode: e.target.value as
                    "RELAXED" | "BALANCED" | "PACKED",
                }))
              }
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-surface)",
                color: "var(--text-primary)",
                fontSize: "13px",
              }}
            >
              <option value="RELAXED">
                Relaxed (1–2 POIs/day, leisurely exploration)
              </option>
              <option value="BALANCED">
                Balanced (3–4 POIs/day, standard sightseeing)
              </option>
              <option value="PACKED">
                Packed (5+ POIs/day, high-tempo adventure)
              </option>
            </select>
          </div>

          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "6px",
              }}
            >
              <label style={{ fontSize: "13px", fontWeight: 700 }}>
                Meal Interval: {plannerForm.meal_interval_hours.toFixed(1)}{" "}
                hours
              </label>
            </div>
            <input
              type="range"
              min={1.0}
              max={8.0}
              step={0.5}
              value={plannerForm.meal_interval_hours}
              onChange={(e) =>
                setPlannerForm((prev) => ({
                  ...prev,
                  meal_interval_hours: parseFloat(e.target.value),
                }))
              }
              style={{ width: "100%" }}
            />
          </div>

          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "6px",
              }}
            >
              <label style={{ fontSize: "13px", fontWeight: 700 }}>
                Max Daily Activity Cap:{" "}
                {plannerForm.max_daily_activity_hours.toFixed(1)} hours
              </label>
            </div>
            <input
              type="range"
              min={1.0}
              max={18.0}
              step={0.5}
              value={plannerForm.max_daily_activity_hours}
              onChange={(e) =>
                setPlannerForm((prev) => ({
                  ...prev,
                  max_daily_activity_hours: parseFloat(e.target.value),
                }))
              }
              style={{ width: "100%" }}
            />
          </div>

          <div>
            <label
              style={{
                fontSize: "13px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Preferred Currency (ISO 4217)
            </label>
            <select
              value={plannerForm.preferred_currency}
              onChange={(e) =>
                setPlannerForm((prev) => ({
                  ...prev,
                  preferred_currency: e.target.value,
                }))
              }
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                background: "var(--bg-surface)",
                color: "var(--text-primary)",
                fontSize: "13px",
              }}
            >
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
              <option value="JPY">JPY (¥)</option>
              <option value="CNY">CNY (¥)</option>
            </select>
          </div>

          <button
            type="button"
            onClick={handleSavePlanner}
            disabled={saving}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              alignSelf: "flex-start",
              padding: "10px 20px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            <Save size={15} />
            <span>{saving ? "Saving..." : "Save Planner Settings"}</span>
          </button>
        </div>
      )}
    </div>
  );
};
