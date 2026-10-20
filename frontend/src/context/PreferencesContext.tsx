// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { apiFetch } from "../services/api";
import { useAuth } from "./AuthContext";
import { useTheme } from "./ThemeContext";

export interface UIPreferences {
  theme: "light" | "dark" | "system";
  email_notifications: boolean;
  push_notifications: boolean;
  marketing_emails: boolean;
}

export interface POIPreferences {
  clustering_enabled: boolean;
  clustering_radius_meters: number;
  default_map_layer: string;
  map_language: string;
  geoproximity_scope_km: number;
  pin_color_presets: {
    not_visited?: string;
    visited_return?: string;
    visited_do_not_return?: string;
    map_language?: string;
    [key: string]: string | undefined;
  };
}

export interface PlannerPreferences {
  pacing_mode: "RELAXED" | "BALANCED" | "PACKED";
  meal_interval_hours: number;
  pack_lunch_preference: boolean;
  default_transit_mode: "WALKING" | "CYCLING" | "TRANSIT" | "DRIVING";
  max_daily_activity_hours: number;
  preferred_currency: string;
}

interface PreferencesContextValue {
  ui: UIPreferences;
  poi: POIPreferences;
  planner: PlannerPreferences;
  isLoading: boolean;
  updateUI: (diff: Partial<UIPreferences>) => Promise<void>;
  updatePOI: (diff: Partial<POIPreferences>) => Promise<void>;
  updatePlanner: (diff: Partial<PlannerPreferences>) => Promise<void>;
}

const defaultUI: UIPreferences = {
  theme: "system",
  email_notifications: true,
  push_notifications: true,
  marketing_emails: false,
};

const defaultPOI: POIPreferences = {
  clustering_enabled: true,
  clustering_radius_meters: 50,
  default_map_layer: "osm",
  map_language: localStorage.getItem("vistarae_map_language") || "local",
  geoproximity_scope_km: 10.0,
  pin_color_presets: {
    not_visited: "#2563eb",
    visited_return: "#10b981",
    visited_do_not_return: "#f59e0b",
  },
};

const defaultPlanner: PlannerPreferences = {
  pacing_mode: "BALANCED",
  meal_interval_hours: 4.0,
  pack_lunch_preference: false,
  default_transit_mode: "WALKING",
  max_daily_activity_hours: 8.0,
  preferred_currency: "USD",
};

const PreferencesContext = createContext<PreferencesContextValue | undefined>(
  undefined,
);

export const PreferencesProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { isAuthenticated } = useAuth();
  const { setTheme } = useTheme();

  const [ui, setUI] = useState<UIPreferences>(defaultUI);
  const [poi, setPOI] = useState<POIPreferences>(defaultPOI);
  const [planner, setPlanner] = useState<PlannerPreferences>(defaultPlanner);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch preferences on login
  const loadPreferences = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    try {
      const [uiRes, poiRes, plannerRes] = await Promise.allSettled([
        apiFetch<UIPreferences>("/api/users/me/preferences/ui"),
        apiFetch<POIPreferences>("/api/users/me/preferences/poi"),
        apiFetch<PlannerPreferences>("/api/users/me/preferences/planner"),
      ]);

      if (uiRes.status === "fulfilled" && uiRes.value) {
        setUI(uiRes.value);
        if (uiRes.value.theme) {
          setTheme(uiRes.value.theme);
        }
      }
      if (poiRes.status === "fulfilled" && poiRes.value) {
        const backendMapLang =
          poiRes.value.pin_color_presets?.map_language ||
          localStorage.getItem("vistarae_map_language") ||
          "local";
        setPOI({
          ...poiRes.value,
          map_language: backendMapLang,
        });
        localStorage.setItem("vistarae_map_language", backendMapLang);
      }
      if (plannerRes.status === "fulfilled" && plannerRes.value) {
        setPlanner(plannerRes.value);
      }
    } catch (err) {
      console.warn("Could not load user preferences from backend:", err);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, setTheme]);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const updateUI = async (diff: Partial<UIPreferences>) => {
    setUI((prev) => ({ ...prev, ...diff }));
    if (diff.theme) {
      setTheme(diff.theme);
    }
    if (isAuthenticated) {
      await apiFetch("/api/users/me/preferences/ui", {
        method: "PATCH",
        body: JSON.stringify(diff),
      });
    }
  };

  const updatePOI = async (diff: Partial<POIPreferences>) => {
    const nextLang = diff.map_language || poi.map_language || "local";
    if (diff.map_language) {
      localStorage.setItem("vistarae_map_language", diff.map_language);
    }
    setPOI((prev) => ({ ...prev, ...diff, map_language: nextLang }));

    if (isAuthenticated) {
      // Pack map_language into pin_color_presets for backend persistence
      const updatedPinPresets = {
        ...(poi.pin_color_presets || {}),
        ...(diff.pin_color_presets || {}),
        map_language: nextLang,
      };

      const { map_language: _, ...backendPayload } = diff;
      await apiFetch("/api/users/me/preferences/poi", {
        method: "PATCH",
        body: JSON.stringify({
          ...backendPayload,
          pin_color_presets: updatedPinPresets,
        }),
      });
    }
  };

  const updatePlanner = async (diff: Partial<PlannerPreferences>) => {
    setPlanner((prev) => ({ ...prev, ...diff }));
    if (isAuthenticated) {
      await apiFetch("/api/users/me/preferences/planner", {
        method: "PATCH",
        body: JSON.stringify(diff),
      });
    }
  };

  return (
    <PreferencesContext.Provider
      value={{
        ui,
        poi,
        planner,
        isLoading,
        updateUI,
        updatePOI,
        updatePlanner,
      }}
    >
      {children}
    </PreferencesContext.Provider>
  );
};

export function usePreferences(): PreferencesContextValue {
  const ctx = useContext(PreferencesContext);
  if (!ctx) {
    throw new Error("usePreferences must be used within a PreferencesProvider");
  }
  return ctx;
}
