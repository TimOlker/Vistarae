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
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { ToastProvider } from "./context/ToastContext";
import { ToastBanner } from "./components/common/ToastBanner";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { PreferencesProvider } from "./context/PreferencesContext";
import { Navbar } from "./components/common/Navbar";
import { AdminRoute } from "./components/common/AdminRoute";

import { HomePage, INITIAL_DEMO_POIS } from "./pages/HomePage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { SignUpPage } from "./pages/SignUpPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SettingsPage } from "./pages/SettingsPage";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { TermsPage } from "./pages/TermsPage";
import { PlannerPage } from "./pages/PlannerPage";
import { ItineraryDetailPage } from "./pages/ItineraryDetailPage";

import { ManualAddPOIModal } from "./components/poi/ManualAddPOIModal";
import { CSVUploadModal } from "./components/ingest/CSVUploadModal";
import { CSVProgressModal } from "./components/ingest/CSVProgressModal";
import { CSVTriageModal } from "./components/ingest/CSVTriageModal";

import { triageStorage } from "./services/triageStorage";
import type { POIMapFeature } from "./types/map";

const AppContent: React.FC = () => {
  const { user, logout } = useAuth();

  const getViewFromPath = (): string => {
    if (typeof window === "undefined") return "home";
    const path = window.location.pathname.replace(/^\/+/, "");
    return path || "home";
  };

  const [currentView, setCurrentView] = useState<string>(() =>
    getViewFromPath(),
  );
  const [resetEmail, setResetEmail] = useState<string>("");

  const navigateTo = React.useCallback((view: string) => {
    setCurrentView(view);
    const targetPath = view === "home" ? "/" : `/${view}`;
    if (
      typeof window !== "undefined" &&
      window.location.pathname !== targetPath
    ) {
      window.history.pushState(null, "", targetPath);
    }
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentView(getViewFromPath());
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // POI state
  const [pois, setPois] = useState<POIMapFeature[]>(INITIAL_DEMO_POIS);

  // Manual POI modal and map-picking state
  const [isAddPOIModalOpen, setIsAddPOIModalOpen] = useState(false);
  const [isPickingLocation, setIsPickingLocation] = useState(false);
  const [pickedCoords, setPickedCoords] = useState<{
    lng: number;
    lat: number;
  } | null>(null);

  // Ingestion workflow modal states
  const [isCSVUploadOpen, setIsCSVUploadOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isCSVProgressOpen, setIsCSVProgressOpen] = useState(false);
  const [isCSVTriageOpen, setIsCSVTriageOpen] = useState(false);
  const [triageJobId, setTriageJobId] = useState<string | null>(null);

  // Opportunistic triage eviction on startup (REQ-UI-027a)
  useEffect(() => {
    triageStorage.evictExpiredRecords().catch((err) => {
      console.warn("Startup triage eviction notice:", err);
    });
  }, []);

  const handleStartPickOnMap = () => {
    setIsAddPOIModalOpen(false);
    setIsPickingLocation(true);
  };

  const handleLocationPicked = (coords: { lng: number; lat: number }) => {
    setPickedCoords(coords);
    setIsPickingLocation(false);
    setIsAddPOIModalOpen(true);
  };

  const handleAddPOI = (newPoi: POIMapFeature) => {
    setPois((prev) => [newPoi, ...prev]);
    setIsAddPOIModalOpen(false);
    setPickedCoords(null);
  };

  const handleJobCreated = (jobId: string) => {
    setIsCSVUploadOpen(false);
    setActiveJobId(jobId);
    setIsCSVProgressOpen(true);
  };

  const handleOpenTriage = (jobId: string) => {
    setIsCSVProgressOpen(false);
    setTriageJobId(jobId);
    setIsCSVTriageOpen(true);
  };

  const handleTriageComplete = () => {
    setIsCSVTriageOpen(false);
    setTriageJobId(null);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100vh",
        width: "100vw",
        background: "var(--bg-primary, #f8fafc)",
        color: "var(--text-primary, #0f172a)",
        overflow: "hidden",
      }}
    >
      <Navbar
        currentView={currentView}
        onNavigate={navigateTo}
        user={user}
        onOpenAddPOI={() => {
          if (!user) {
            navigateTo("login");
            return;
          }
          setIsAddPOIModalOpen(true);
        }}
        onOpenUploadCSV={() => {
          if (!user) {
            navigateTo("login");
            return;
          }
          setIsCSVUploadOpen(true);
        }}
        onLogout={async () => {
          await logout();
          navigateTo("home");
        }}
      />

      <ToastBanner />

      {/* Main View Router */}
      <div style={{ flex: 1, position: "relative", overflow: "auto" }}>
        {currentView === "home" &&
          (user ? (
            <HomePage
              pois={pois}
              onUpdatePois={setPois}
              isPickingLocation={isPickingLocation}
              onLocationPicked={handleLocationPicked}
            />
          ) : (
            <LandingPage
              onNavigateLogin={() => navigateTo("login")}
              onNavigateSignUp={() => navigateTo("signup")}
              onNavigateTerms={() => navigateTo("terms")}
            />
          ))}

        {currentView === "login" && (
          <LoginPage
            onSuccess={() => navigateTo("home")}
            onNavigateSignUp={() => navigateTo("signup")}
            onNavigateForgotPassword={() => navigateTo("forgot-password")}
          />
        )}

        {currentView === "signup" && (
          <SignUpPage
            onSuccess={() => navigateTo("login")}
            onNavigateLogin={() => navigateTo("login")}
          />
        )}

        {currentView === "forgot-password" && (
          <ForgotPasswordPage
            onCodeSent={(email) => {
              setResetEmail(email);
              navigateTo("reset-password");
            }}
            onNavigateLogin={() => navigateTo("login")}
          />
        )}

        {currentView === "reset-password" && (
          <ResetPasswordPage
            email={resetEmail}
            onSuccess={() => navigateTo("login")}
          />
        )}

        {currentView === "profile" &&
          (user ? (
            <ProfilePage onAccountDeleted={() => navigateTo("home")} />
          ) : (
            <LoginPage
              onSuccess={() => navigateTo("profile")}
              onNavigateSignUp={() => navigateTo("signup")}
              onNavigateForgotPassword={() => navigateTo("forgot-password")}
            />
          ))}

        {currentView === "settings" &&
          (user ? (
            <SettingsPage initialTab="account" />
          ) : (
            <LoginPage
              onSuccess={() => navigateTo("settings")}
              onNavigateSignUp={() => navigateTo("signup")}
              onNavigateForgotPassword={() => navigateTo("forgot-password")}
            />
          ))}
        {currentView === "settings/account" &&
          (user ? (
            <SettingsPage initialTab="account" />
          ) : (
            <LoginPage
              onSuccess={() => navigateTo("settings/account")}
              onNavigateSignUp={() => navigateTo("signup")}
              onNavigateForgotPassword={() => navigateTo("forgot-password")}
            />
          ))}
        {currentView === "settings/poi" &&
          (user ? (
            <SettingsPage initialTab="poi" />
          ) : (
            <LoginPage
              onSuccess={() => navigateTo("settings/poi")}
              onNavigateSignUp={() => navigateTo("signup")}
              onNavigateForgotPassword={() => navigateTo("forgot-password")}
            />
          ))}
        {currentView === "settings/planner" &&
          (user ? (
            <SettingsPage initialTab="planner" />
          ) : (
            <LoginPage
              onSuccess={() => navigateTo("settings/planner")}
              onNavigateSignUp={() => navigateTo("signup")}
              onNavigateForgotPassword={() => navigateTo("forgot-password")}
            />
          ))}

        {(currentView === "planner" || currentView === "trips") &&
          (user ? (
            <PlannerPage
              onNavigateToTrip={(itineraryId) =>
                navigateTo(`trips/${itineraryId}`)
              }
            />
          ) : (
            <LoginPage
              onSuccess={() => navigateTo("planner")}
              onNavigateSignUp={() => navigateTo("signup")}
              onNavigateForgotPassword={() => navigateTo("forgot-password")}
            />
          ))}

        {currentView.startsWith("trips/") &&
          (user ? (
            <ItineraryDetailPage
              itineraryId={currentView.slice("trips/".length)}
              onNavigateBack={() => navigateTo("planner")}
            />
          ) : (
            <LoginPage
              onSuccess={() => navigateTo(currentView)}
              onNavigateSignUp={() => navigateTo("signup")}
              onNavigateForgotPassword={() => navigateTo("forgot-password")}
            />
          ))}

        {currentView === "admin" && (
          <AdminRoute onUnauthorizedRedirect={() => navigateTo("home")}>
            <AdminDashboardPage />
          </AdminRoute>
        )}

        {currentView === "terms" && (
          <TermsPage onNavigateHome={() => navigateTo("home")} />
        )}
      </div>

      {/* Modals & Dialogs */}
      <ManualAddPOIModal
        isOpen={isAddPOIModalOpen}
        onClose={() => {
          setIsAddPOIModalOpen(false);
          setIsPickingLocation(false);
          setPickedCoords(null);
        }}
        onAddPOI={handleAddPOI}
        onStartPickOnMap={handleStartPickOnMap}
        pickedCoords={pickedCoords}
      />

      <CSVUploadModal
        isOpen={isCSVUploadOpen}
        onClose={() => setIsCSVUploadOpen(false)}
        onJobCreated={handleJobCreated}
      />

      <CSVProgressModal
        jobId={activeJobId}
        isOpen={isCSVProgressOpen}
        onClose={() => setIsCSVProgressOpen(false)}
        onOpenTriage={handleOpenTriage}
        onJobComplete={() => {
          setIsCSVProgressOpen(false);
          setActiveJobId(null);
        }}
      />

      <CSVTriageModal
        jobId={triageJobId}
        isOpen={isCSVTriageOpen}
        onClose={() => {
          setIsCSVTriageOpen(false);
          setTriageJobId(null);
        }}
        onTriageComplete={handleTriageComplete}
      />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <ThemeProvider>
          <AuthProvider>
            <PreferencesProvider>
              <AppContent />
            </PreferencesProvider>
          </AuthProvider>
        </ThemeProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
};

export default App;
