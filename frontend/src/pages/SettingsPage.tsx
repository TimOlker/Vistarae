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

// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState, useEffect } from "react";
import { usePreferences } from "../context/PreferencesContext";
import { useToast } from "../context/ToastContext";
import { Palette, Map, Calendar, Save, Tag, Globe, Plus, Trash2 } from "lucide-react";
import { ThemeSwitcher } from "../components/common/ThemeSwitcher";
import { TagManager } from "../components/tags/TagManager";

export type SettingsTab = "account" | "poi" | "planner" | "tags" | "scraping";

export const SettingsPage: React.FC<{ initialTab?: SettingsTab }> = ({
  initialTab = "account",
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);
  const {
    ui,
    poi,
    planner,
    validScrapingDomains,
    updateUI,
    updatePOI,
    updatePlanner,
    updateScrapingDomains,
  } = usePreferences();
  const { showToast } = useToast();

  const [saving, setSaving] = useState(false);

  // Local form states
  const [uiForm, setUiForm] = useState(ui);
  const [poiForm, setPoiForm] = useState(poi);
  const [plannerForm, setPlannerForm] = useState(planner);
  const [scrapingDomains, setScrapingDomains] = useState<string[]>(
    validScrapingDomains || [],
  );
  const [newDomainInput, setNewDomainInput] = useState("");

  useEffect(() => {
    if (validScrapingDomains) {
      setScrapingDomains(validScrapingDomains);
    }
  }, [validScrapingDomains]);

  const handleAddDomain = () => {
    const trimmed = newDomainInput.trim().toLowerCase();
    if (!trimmed) return;
    if (scrapingDomains.includes(trimmed)) {
      showToast("Domain already authorized", "info");
      return;
    }
    setScrapingDomains((prev) => [...prev, trimmed]);
    setNewDomainInput("");
  };

  const handleRemoveDomain = (domainToRemove: string) => {
    if (scrapingDomains.length <= 1) {
      showToast(
        "At least one scraping source domain must remain authorized",
        "error",
      );
      return;
    }
    setScrapingDomains((prev) => prev.filter((d) => d !== domainToRemove));
  };

  const handleSaveScraping = async () => {
    setSaving(true);
    try {
      await updateScrapingDomains(scrapingDomains);
      showToast("Scraping sources preferences saved!", "success");
    } catch {
      showToast("Failed to save scraping sources", "error");
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    setUiForm(ui);
  }, [ui]);

  useEffect(() => {
    setPoiForm(poi);
  }, [poi]);

  useEffect(() => {
    setPlannerForm(planner);
  }, [planner]);

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

        <button
          type="button"
          onClick={() => setActiveTab("tags")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 16px",
            borderBottom:
              activeTab === "tags"
                ? "2px solid var(--accent, #2563eb)"
                : "2px solid transparent",
            color:
              activeTab === "tags"
                ? "var(--accent, #2563eb)"
                : "var(--text-secondary, #64748b)",
            fontWeight: 600,
            fontSize: "14px",
          }}
        >
          <Tag size={16} />
          <span>Tags Library</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("scraping")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 16px",
            borderBottom:
              activeTab === "scraping"
                ? "2px solid var(--accent, #2563eb)"
                : "2px solid transparent",
            color:
              activeTab === "scraping"
                ? "var(--accent, #2563eb)"
                : "var(--text-secondary, #64748b)",
            fontWeight: 600,
            fontSize: "14px",
          }}
        >
          <Globe size={16} />
          <span>Scraping Sources</span>
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
            <div
              style={{
                display: "flex",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "14px",
              }}
            >
              <ThemeSwitcher
                value={uiForm.theme}
                onChange={(mode) =>
                  setUiForm((prev) => ({
                    ...prev,
                    theme: mode,
                  }))
                }
              />
              <span
                style={{
                  fontSize: "12px",
                  color: "var(--text-muted, #64748b)",
                }}
              >
                {uiForm.theme === "system"
                  ? "Follows your operating system's appearance automatically."
                  : uiForm.theme === "dark"
                    ? "Dark mode active across all maps, tables, and dialogs."
                    : "Light mode active across all maps, tables, and dialogs."}
              </span>
            </div>
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
              <option value="openfreemap">OpenFreeMap (English Vector)</option>
              <option value="satellite">Satellite (Esri)</option>
              <option value="road">Road (CartoDB)</option>
              <option value="google-roadmap">Google Maps</option>
              <option value="google-hybrid">Google Hybrid</option>
              <option value="amap">AutoNavi / Amap (GCJ-02)</option>
              <option value="baidu">Baidu Maps (BD-09)</option>
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label
              style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "var(--text-primary)",
              }}
            >
              Map Label Language
            </label>
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              Choose whether map tiles display native local place names or force
              translations (e.g., &quot;Eiffel Tower&quot; vs &quot;Tour
              Eiffel&quot;).
            </span>
            <select
              value={poiForm.map_language || "local"}
              onChange={(e) =>
                setPoiForm((prev) => ({
                  ...prev,
                  map_language: e.target.value,
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
              <option value="local">
                Local Language (Default - Native names)
              </option>
              <option value="en">English (Force English translations)</option>
              <option value="es">Spanish (Español)</option>
              <option value="fr">French (Français)</option>
              <option value="de">German (Deutsch)</option>
              <option value="zh">Chinese (中文)</option>
              <option value="ja">Japanese (日本語)</option>
              <option value="ko">Korean (한국어)</option>
              <option value="it">Italian (Italiano)</option>
              <option value="pt">Portuguese (Português)</option>
              <option value="ru">Russian (Русский)</option>
              <option value="ar">Arabic (العربية)</option>
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
                    | "RELAXED"
                    | "BALANCED"
                    | "PACKED",
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
              Preferred Currency
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

      {/* Tags Library Tab */}
      {activeTab === "tags" && (
        <div className="slide-up">
          <TagManager />
        </div>
      )}

      {/* Scraping Sources Tab */}
      {activeTab === "scraping" && (
        <div
          className="slide-up"
          style={{
            background: "var(--bg-surface, #ffffff)",
            borderRadius: "var(--radius-lg, 16px)",
            border: "1px solid var(--border-color, #e2e8f0)",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          <div>
            <h2
              style={{
                fontSize: "16px",
                fontWeight: 700,
                margin: "0 0 6px 0",
              }}
            >
              Authorized Secondary Scraping Sources
            </h2>
            <p
              style={{
                fontSize: "13px",
                color: "var(--text-secondary, #64748b)",
                margin: 0,
              }}
            >
              Specify the domain suffixes authorized for automated secondary POI
              scraping and augmentation (REQ-EXT-019).
            </p>
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <input
              type="text"
              placeholder="e.g. timeout.com"
              value={newDomainInput}
              onChange={(e) => setNewDomainInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddDomain();
                }
              }}
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
                background: "var(--bg-surface)",
                color: "var(--text-primary)",
              }}
            />
            <button
              type="button"
              onClick={handleAddDomain}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "8px 16px",
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--accent, #2563eb)",
                color: "#ffffff",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor: "pointer",
              }}
            >
              <Plus size={15} />
              <span>Add Domain</span>
            </button>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "var(--radius-md, 8px)",
              padding: "12px",
            }}
          >
            {scrapingDomains.map((domain) => (
              <div
                key={domain}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  background: "var(--bg-muted, #f8fafc)",
                  borderRadius: "6px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <Globe size={14} color="var(--text-secondary, #64748b)" />
                  <span
                    style={{
                      fontSize: "13px",
                      fontFamily: "monospace",
                      fontWeight: 600,
                    }}
                  >
                    {domain}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveDomain(domain)}
                  title="Remove domain"
                  style={{
                    border: "none",
                    background: "transparent",
                    color: "var(--text-muted, #94a3b8)",
                    cursor: "pointer",
                    padding: "4px",
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={handleSaveScraping}
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
              border: "none",
              cursor: "pointer",
            }}
          >
            <Save size={15} />
            <span>{saving ? "Saving..." : "Save Scraping Sources"}</span>
          </button>
        </div>
      )}
    </div>
  );
};
