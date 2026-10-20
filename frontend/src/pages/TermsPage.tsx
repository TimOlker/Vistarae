// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React from "react";
import { ShieldCheck, ArrowLeft } from "lucide-react";

export const TermsPage: React.FC<{ onNavigateHome?: () => void }> = ({
  onNavigateHome,
}) => {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--bg-primary, #f8fafc)",
        color: "var(--text-primary, #0f172a)",
        padding: "32px 16px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div style={{ maxWidth: "760px", width: "100%" }}>
        {onNavigateHome && (
          <button
            type="button"
            onClick={onNavigateHome}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "var(--radius-sm, 6px)",
              background: "var(--bg-hover, #f1f5f9)",
              color: "var(--text-secondary, #475569)",
              fontSize: "13px",
              fontWeight: 600,
              marginBottom: "24px",
            }}
          >
            <ArrowLeft size={16} />
            <span>Back to Home</span>
          </button>
        )}

        <div
          style={{
            background: "var(--bg-surface, #ffffff)",
            borderRadius: "var(--radius-lg, 16px)",
            boxShadow: "var(--shadow-md)",
            border: "1px solid var(--border-color, #e2e8f0)",
            padding: "36px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              marginBottom: "8px",
            }}
          >
            <ShieldCheck size={28} color="var(--accent, #2563eb)" />
            <h1 style={{ fontSize: "24px", fontWeight: 800 }}>
              Terms of Service & Privacy
            </h1>
          </div>
          <p
            style={{
              fontSize: "13px",
              color: "var(--text-muted)",
              marginBottom: "24px",
            }}
          >
            Last updated: October 2026 • Vistarae Travel Architecture
          </p>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "24px",
              fontSize: "14px",
              lineHeight: 1.6,
            }}
          >
            <section>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 700,
                  marginBottom: "8px",
                }}
              >
                1. Privacy-First, Zero-Cloud Photo Ingestion
              </h2>
              <p style={{ color: "var(--text-secondary)" }}>
                Vistarae utilizes a zero-cost, privacy-first architecture. When
                you select or drop a photo to extract location metadata, all
                EXIF processing executes{" "}
                <strong>entirely within your browser's local memory</strong>.
                Your photo binary files are never transmitted to our backend
                servers, Amazon S3, or third-party cloud AI vendors.
              </p>
            </section>

            <section>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 700,
                  marginBottom: "8px",
                }}
              >
                2. Geocoding & Coordinate Governance
              </h2>
              <p style={{ color: "var(--text-secondary)" }}>
                Coordinates stored in your personal account are kept strictly in
                canonical WGS-84 format (EPSG:4326). When viewing maps over
                regional Chinese satellite or vector layers, coordinate
                transformations (GCJ-02 and BD-09) occur strictly inside your
                browser. We never share your travel history, pin drops, or
                itinerary coordinates with ad networks.
              </p>
            </section>

            <section>
              <h2
                style={{
                  fontSize: "16px",
                  fontWeight: 700,
                  marginBottom: "8px",
                }}
              >
                3. Tenant Isolation & GDPR Cascade Deletion
              </h2>
              <p style={{ color: "var(--text-secondary)" }}>
                Every Point of Interest, list, and ingestion job is strictly
                partitioned by your tenant UUID. You maintain full ownership of
                your data. You may export your POI collection at any time, or
                request complete cascade deletion under GDPR compliance from
                your Profile page.
              </p>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
};
