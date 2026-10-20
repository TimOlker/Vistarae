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
import { LoginPage } from "./pages/LoginPage";
import { SignUpPage } from "./pages/SignUpPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SettingsPage } from "./pages/SettingsPage";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { TermsPage } from "./pages/TermsPage";

import { ManualAddPOIModal } from "./components/poi/ManualAddPOIModal";
import { CSVUploadModal } from "./components/ingest/CSVUploadModal";
import { CSVProgressModal } from "./components/ingest/CSVProgressModal";
import { CSVTriageModal } from "./components/ingest/CSVTriageModal";

import { triageStorage } from "./services/triageStorage";
import type { POIMapFeature } from "./types/map";

const AppContent: React.FC = () => {
  const { user, logout } = useAuth();
  const [currentView, setCurrentView] = useState<string>("home");
  const [resetEmail, setResetEmail] = useState<string>("");

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
        onNavigate={setCurrentView}
        user={user}
        onOpenAddPOI={() => setIsAddPOIModalOpen(true)}
        onOpenUploadCSV={() => setIsCSVUploadOpen(true)}
        onLogout={async () => {
          await logout();
          setCurrentView("home");
        }}
      />

      <ToastBanner />

      {/* Main View Router */}
      <div style={{ flex: 1, position: "relative", overflow: "auto" }}>
        {currentView === "home" && (
          <HomePage
            pois={pois}
            onUpdatePois={setPois}
            isPickingLocation={isPickingLocation}
            onLocationPicked={handleLocationPicked}
          />
        )}

        {currentView === "login" && (
          <LoginPage
            onSuccess={() => setCurrentView("home")}
            onNavigateSignUp={() => setCurrentView("signup")}
            onNavigateForgotPassword={() => setCurrentView("forgot-password")}
          />
        )}

        {currentView === "signup" && (
          <SignUpPage
            onSuccess={() => setCurrentView("login")}
            onNavigateLogin={() => setCurrentView("login")}
          />
        )}

        {currentView === "forgot-password" && (
          <ForgotPasswordPage
            onCodeSent={(email) => {
              setResetEmail(email);
              setCurrentView("reset-password");
            }}
            onNavigateLogin={() => setCurrentView("login")}
          />
        )}

        {currentView === "reset-password" && (
          <ResetPasswordPage
            email={resetEmail}
            onSuccess={() => setCurrentView("login")}
          />
        )}

        {currentView === "profile" && (
          <ProfilePage onAccountDeleted={() => setCurrentView("home")} />
        )}

        {currentView === "settings" && <SettingsPage initialTab="account" />}
        {currentView === "settings/account" && (
          <SettingsPage initialTab="account" />
        )}
        {currentView === "settings/poi" && <SettingsPage initialTab="poi" />}
        {currentView === "settings/planner" && (
          <SettingsPage initialTab="planner" />
        )}

        {currentView === "admin" && (
          <AdminRoute onUnauthorizedRedirect={() => setCurrentView("home")}>
            <AdminDashboardPage />
          </AdminRoute>
        )}

        {currentView === "terms" && (
          <TermsPage onNavigateHome={() => setCurrentView("home")} />
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
