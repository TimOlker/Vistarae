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

import React, { useState } from "react";
import {
  MapPin,
  Sparkles,
  Layers,
  Globe,
  UploadCloud,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  LogIn,
  UserPlus,
  Star,
  Cpu,
  Bookmark,
  ChevronRight,
} from "lucide-react";

export interface LandingPageProps {
  onNavigateLogin: () => void;
  onNavigateSignUp: () => void;
  onNavigateTerms?: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onNavigateLogin,
  onNavigateSignUp,
  onNavigateTerms,
}) => {
  const [activeTab, setActiveTab] = useState<"capture" | "maps" | "triage">(
    "capture",
  );

  return (
    <div
      style={{
        minHeight: "100%",
        width: "100%",
        background: "var(--bg-primary, #f8fafc)",
        color: "var(--text-primary, #0f172a)",
        display: "flex",
        flexDirection: "column",
        overflowX: "hidden",
      }}
    >
      {/* Hero Section */}
      <section
        style={{
          position: "relative",
          padding: "64px 24px 80px 24px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          background:
            "radial-gradient(ellipse 80% 50% at 50% -10%, rgba(37, 99, 235, 0.15), transparent 70%)",
        }}
      >
        {/* Shimmering Badge */}
        <div
          className="slide-up"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 16px",
            borderRadius: "var(--radius-full, 9999px)",
            background: "var(--accent-light, #eff6ff)",
            border: "1px solid rgba(37, 99, 235, 0.25)",
            color: "var(--accent, #2563eb)",
            fontSize: "13px",
            fontWeight: 700,
            marginBottom: "24px",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <Sparkles size={15} />
          <span>Next-Generation Travel & POI Capture Engine</span>
        </div>

        {/* Hero Title */}
        <h1
          className="slide-up"
          style={{
            fontSize: "clamp(32px, 5.5vw, 58px)",
            fontWeight: 900,
            lineHeight: 1.15,
            letterSpacing: "-0.03em",
            maxWidth: "920px",
            marginBottom: "20px",
          }}
        >
          Capture Every Scenic Overlook, Hidden Trail &{" "}
          <span
            style={{
              background: "linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Travel Dream
          </span>
        </h1>

        {/* Subtitle */}
        <p
          className="slide-up"
          style={{
            fontSize: "clamp(16px, 2vw, 19px)",
            color: "var(--text-secondary, #475569)",
            maxWidth: "740px",
            lineHeight: 1.6,
            marginBottom: "36px",
          }}
        >
          Turn travel blogs, scenic coordinates, and web discoveries into rich,
          geocoded points of interest with multi-layer maps, intelligent
          deduplication, and zero-latency AI extraction.
        </p>

        {/* CTA Buttons */}
        <div
          className="slide-up"
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "14px",
            justifyContent: "center",
            alignItems: "center",
            marginBottom: "24px",
          }}
        >
          <button
            type="button"
            onClick={onNavigateSignUp}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "14px 28px",
              borderRadius: "var(--radius-md, 10px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontSize: "15px",
              fontWeight: 700,
              boxShadow: "0 10px 25px -5px rgba(37, 99, 235, 0.4)",
              transition: "transform 150ms ease, box-shadow 150ms ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow =
                "0 14px 28px -4px rgba(37, 99, 235, 0.5)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow =
                "0 10px 25px -5px rgba(37, 99, 235, 0.4)";
            }}
          >
            <UserPlus size={18} />
            <span>Get Started Free</span>
            <ArrowRight size={16} />
          </button>

          <button
            type="button"
            onClick={onNavigateLogin}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "14px 26px",
              borderRadius: "var(--radius-md, 10px)",
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #cbd5e1)",
              color: "var(--text-primary, #0f172a)",
              fontSize: "15px",
              fontWeight: 700,
              boxShadow: "var(--shadow-sm)",
              transition: "background 150ms ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-hover, #f1f5f9)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--bg-surface, #ffffff)";
            }}
          >
            <LogIn size={17} />
            <span>Sign In to Workspace</span>
          </button>
        </div>

        {/* Trust Badges */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "20px",
            justifyContent: "center",
            fontSize: "13px",
            color: "var(--text-muted, #94a3b8)",
            fontWeight: 500,
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <CheckCircle2 size={15} color="#10b981" /> Free tier available
          </span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <CheckCircle2 size={15} color="#10b981" /> No credit card required
          </span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <CheckCircle2 size={15} color="#10b981" /> Manifest V3 Chrome
            Extension
          </span>
        </div>

        {/* Hero Interactive App Mockup Showcase */}
        <div
          style={{
            width: "100%",
            maxWidth: "1060px",
            marginTop: "48px",
            borderRadius: "var(--radius-lg, 16px)",
            background: "var(--bg-surface, #ffffff)",
            border: "1px solid var(--border-color, #e2e8f0)",
            boxShadow:
              "0 25px 50px -12px rgba(15, 23, 42, 0.18), 0 0 0 1px rgba(0, 0, 0, 0.05)",
            overflow: "hidden",
            textAlign: "left",
          }}
        >
          {/* Mock Window Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "12px 18px",
              background: "var(--bg-hover, #f1f5f9)",
              borderBottom: "1px solid var(--border-color, #e2e8f0)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "11px",
                  height: "11px",
                  borderRadius: "50%",
                  background: "#ef4444",
                }}
              />
              <div
                style={{
                  width: "11px",
                  height: "11px",
                  borderRadius: "50%",
                  background: "#f59e0b",
                }}
              />
              <div
                style={{
                  width: "11px",
                  height: "11px",
                  borderRadius: "50%",
                  background: "#10b981",
                }}
              />
              <span
                style={{
                  marginLeft: "12px",
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "var(--text-secondary)",
                }}
              >
                Vistarae Explorer — Paris, France (OpenFreeMap Vector)
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  fontSize: "11px",
                  padding: "3px 8px",
                  borderRadius: "var(--radius-full, 9999px)",
                  background: "var(--accent-light, #eff6ff)",
                  color: "var(--accent, #2563eb)",
                  fontWeight: 700,
                }}
              >
                ● 24 POIs Synchronized
              </span>
            </div>
          </div>

          {/* Mock Window Body */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              minHeight: "360px",
            }}
          >
            {/* Left: Map Preview Canvas */}
            <div
              style={{
                position: "relative",
                background:
                  "linear-gradient(145deg, #1e293b 0%, #0f172a 50%, #1e1e38 100%)",
                padding: "24px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                overflow: "hidden",
              }}
            >
              {/* Subtle Map Grid lines */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  backgroundImage:
                    "radial-gradient(rgba(255, 255, 255, 0.1) 1px, transparent 1px)",
                  backgroundSize: "28px 28px",
                  opacity: 0.6,
                }}
              />

              {/* Map Layer Tag */}
              <div
                style={{
                  position: "relative",
                  zIndex: 2,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "5px 12px",
                  borderRadius: "var(--radius-full, 9999px)",
                  background: "rgba(15, 23, 42, 0.75)",
                  backdropFilter: "blur(8px)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  color: "#ffffff",
                  fontSize: "12px",
                  fontWeight: 600,
                  alignSelf: "flex-start",
                }}
              >
                <Layers size={13} color="#60a5fa" />
                <span>OpenFreeMap (English Vector)</span>
              </div>

              {/* Simulated Map Markers */}
              <div
                style={{
                  position: "relative",
                  zIndex: 2,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "16px",
                  padding: "30px 0",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                  }}
                >
                  {/* Cluster circle */}
                  <div
                    style={{
                      width: "48px",
                      height: "48px",
                      borderRadius: "50%",
                      background: "#3b82f6",
                      border: "3px solid #ffffff",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#ffffff",
                      fontWeight: 800,
                      fontSize: "15px",
                      boxShadow: "0 0 20px rgba(59, 130, 246, 0.6)",
                    }}
                  >
                    18
                  </div>

                  {/* Active Pin */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "8px 14px",
                      borderRadius: "var(--radius-full, 9999px)",
                      background: "rgba(255, 255, 255, 0.95)",
                      color: "#0f172a",
                      fontWeight: 700,
                      fontSize: "13px",
                      boxShadow: "0 8px 24px rgba(0, 0, 0, 0.3)",
                    }}
                  >
                    <span
                      style={{
                        width: "10px",
                        height: "10px",
                        borderRadius: "50%",
                        background: "#10b981",
                      }}
                    />
                    <span>Eiffel Tower</span>
                  </div>
                </div>

                <div
                  style={{
                    fontSize: "12px",
                    color: "rgba(255, 255, 255, 0.7)",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <MapPin size={13} color="#10b981" />
                  <span>48.8584° N, 2.2945° E · Canonical WGS-84</span>
                </div>
              </div>

              {/* Bottom hint */}
              <div
                style={{
                  position: "relative",
                  zIndex: 2,
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "11px",
                  color: "rgba(255, 255, 255, 0.6)",
                }}
              >
                <span>60 FPS Supercluster</span>
                <span>Zoom Level 14.5</span>
              </div>
            </div>

            {/* Right: Rich POI Detail Card */}
            <div
              style={{
                padding: "24px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                background: "var(--bg-surface, #ffffff)",
                borderLeft: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "12px",
                  }}
                >
                  <div>
                    <span
                      style={{
                        display: "inline-block",
                        fontSize: "11px",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: "var(--accent, #2563eb)",
                        marginBottom: "4px",
                      }}
                    >
                      Point of Interest
                    </span>
                    <h3 style={{ fontSize: "20px", fontWeight: 800 }}>
                      Eiffel Tower
                    </h3>
                  </div>

                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      padding: "4px 10px",
                      borderRadius: "var(--radius-full, 9999px)",
                      background: "#ecfdf5",
                      color: "#059669",
                      fontSize: "12px",
                      fontWeight: 700,
                    }}
                  >
                    <CheckCircle2 size={13} /> Visited (Return)
                  </span>
                </div>

                <p
                  style={{
                    fontSize: "13px",
                    color: "var(--text-secondary)",
                    lineHeight: 1.5,
                    marginBottom: "16px",
                  }}
                >
                  Iconic 330m-high 19th-century wrought-iron lattice tower on
                  the Champ de Mars in Paris. Captured directly from web travel
                  notes.
                </p>

                {/* Rating & Tags */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "14px",
                  }}
                >
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "3px",
                      padding: "3px 8px",
                      borderRadius: "var(--radius-sm, 6px)",
                      background: "#fef3c7",
                      color: "#b45309",
                      fontSize: "12px",
                      fontWeight: 700,
                    }}
                  >
                    <Star size={13} fill="#b45309" color="#b45309" /> 5.0
                  </div>
                  <span
                    style={{
                      fontSize: "12px",
                      color: "var(--text-muted)",
                    }}
                  >
                    Paris, France
                  </span>
                </div>

                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "6px",
                    marginBottom: "18px",
                  }}
                >
                  {["#landmark", "#viewpoint", "#architecture", "#unesco"].map(
                    (tag) => (
                      <span
                        key={tag}
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          padding: "2px 8px",
                          borderRadius: "var(--radius-sm, 6px)",
                          background: "var(--bg-hover, #f1f5f9)",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {tag}
                      </span>
                    ),
                  )}
                </div>
              </div>

              {/* Card Footer with CTA */}
              <div
                style={{
                  paddingTop: "16px",
                  borderTop: "1px solid var(--border-color, #e2e8f0)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  Captured via Chrome Extension
                </span>
                <button
                  type="button"
                  onClick={onNavigateSignUp}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "5px",
                    fontSize: "12px",
                    fontWeight: 700,
                    color: "var(--accent, #2563eb)",
                  }}
                >
                  <span>Explore in App</span>
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Value Metrics Strip */}
      <section
        style={{
          padding: "32px 24px",
          background: "var(--bg-surface, #ffffff)",
          borderTop: "1px solid var(--border-color, #e2e8f0)",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
        }}
      >
        <div
          style={{
            maxWidth: "1060px",
            margin: "0 auto",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "24px",
            textAlign: "center",
          }}
        >
          <div>
            <div
              style={{
                fontSize: "32px",
                fontWeight: 900,
                color: "var(--accent, #2563eb)",
                letterSpacing: "-0.03em",
              }}
            >
              8+
            </div>
            <div
              style={{ fontSize: "14px", fontWeight: 700, marginTop: "2px" }}
            >
              Multi-Engine Map Layers
            </div>
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginTop: "2px",
              }}
            >
              OpenFreeMap Vector, OSM, Google, ESRI
            </div>
          </div>

          <div>
            <div
              style={{
                fontSize: "32px",
                fontWeight: 900,
                color: "var(--accent, #2563eb)",
                letterSpacing: "-0.03em",
              }}
            >
              60 FPS
            </div>
            <div
              style={{ fontSize: "14px", fontWeight: 700, marginTop: "2px" }}
            >
              Supercluster Engine
            </div>
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginTop: "2px",
              }}
            >
              Instant client clustering up to 10k pins
            </div>
          </div>

          <div>
            <div
              style={{
                fontSize: "32px",
                fontWeight: 900,
                color: "var(--accent, #2563eb)",
                letterSpacing: "-0.03em",
              }}
            >
              100%
            </div>
            <div
              style={{ fontSize: "14px", fontWeight: 700, marginTop: "2px" }}
            >
              Canonical WGS-84
            </div>
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginTop: "2px",
              }}
            >
              Automatic GCJ-02 & BD-09 shift correction
            </div>
          </div>

          <div>
            <div
              style={{
                fontSize: "32px",
                fontWeight: 900,
                color: "var(--accent, #2563eb)",
                letterSpacing: "-0.03em",
              }}
            >
              &lt; 1s
            </div>
            <div
              style={{ fontSize: "14px", fontWeight: 700, marginTop: "2px" }}
            >
              AI Entity Extraction
            </div>
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                marginTop: "2px",
              }}
            >
              Gemini Flash-Lite structured JSON parsing
            </div>
          </div>
        </div>
      </section>

      {/* Core Features Grid */}
      <section
        id="features"
        style={{
          padding: "80px 24px",
          maxWidth: "1140px",
          margin: "0 auto",
          width: "100%",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "56px" }}>
          <span
            style={{
              fontSize: "13px",
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--accent, #2563eb)",
              display: "block",
              marginBottom: "8px",
            }}
          >
            Built for Modern Explorers
          </span>
          <h2
            style={{
              fontSize: "clamp(26px, 4vw, 38px)",
              fontWeight: 800,
              letterSpacing: "-0.02em",
            }}
          >
            Everything You Need to Capture & Map the World
          </h2>
          <p
            style={{
              fontSize: "16px",
              color: "var(--text-secondary)",
              maxWidth: "640px",
              margin: "12px auto 0 auto",
            }}
          >
            A cohesive suite of tools designed to preserve your travel dreams
            with extreme geospatial precision.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: "24px",
          }}
        >
          {/* Card 1 */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "var(--radius-lg, 16px)",
              padding: "28px",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 200ms ease, box-shadow 200ms ease",
            }}
          >
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md, 10px)",
                background: "var(--accent-light, #eff6ff)",
                color: "var(--accent, #2563eb)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "18px",
              }}
            >
              <Globe size={22} />
            </div>
            <h3
              style={{ fontSize: "18px", fontWeight: 700, marginBottom: "8px" }}
            >
              One-Click Browser Capture
            </h3>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                lineHeight: 1.6,
              }}
            >
              Clip scenic overlooks, hiking trails, and travel blogs directly
              from your browser with Manifest V3. Keyboard shortcut{" "}
              <code>Ctrl+Shift+S</code> seamlessly triggers contextual capture.
            </p>
          </div>

          {/* Card 2 */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "var(--radius-lg, 16px)",
              padding: "28px",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 200ms ease, box-shadow 200ms ease",
            }}
          >
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md, 10px)",
                background: "#ecfdf5",
                color: "#10b981",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "18px",
              }}
            >
              <Layers size={22} />
            </div>
            <h3
              style={{ fontSize: "18px", fontWeight: 700, marginBottom: "8px" }}
            >
              OpenFreeMap & Multi-Engine Maps
            </h3>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                lineHeight: 1.6,
              }}
            >
              Render OpenFreeMap vector styles with true English landmark labels
              worldwide, or switch freely between OpenStreetMap, Google Hybrid,
              ESRI World Imagery, and AutoNavi.
            </p>
          </div>

          {/* Card 3 */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "var(--radius-lg, 16px)",
              padding: "28px",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 200ms ease, box-shadow 200ms ease",
            }}
          >
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md, 10px)",
                background: "#fef3c7",
                color: "#d97706",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "18px",
              }}
            >
              <Cpu size={22} />
            </div>
            <h3
              style={{ fontSize: "18px", fontWeight: 700, marginBottom: "8px" }}
            >
              Zero-Latency AI Geocoding
            </h3>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                lineHeight: 1.6,
              }}
            >
              Powered by Gemini Flash-Lite with zero thinking budget for fast,
              deterministic entity parsing. Extracts venue names, addresses,
              ratings, and tags with structured Pydantic precision.
            </p>
          </div>

          {/* Card 4 */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "var(--radius-lg, 16px)",
              padding: "28px",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 200ms ease, box-shadow 200ms ease",
            }}
          >
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md, 10px)",
                background: "#ede9fe",
                color: "#7c3aed",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "18px",
              }}
            >
              <UploadCloud size={22} />
            </div>
            <h3
              style={{ fontSize: "18px", fontWeight: 700, marginBottom: "8px" }}
            >
              Bulk CSV Ingest & Triage
            </h3>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                lineHeight: 1.6,
              }}
            >
              Drag-and-drop location spreadsheets. Our async engine
              automatically maps custom columns, detects duplicates, splits
              multi-location entries, and provides offline triage via IndexedDB.
            </p>
          </div>

          {/* Card 5 */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "var(--radius-lg, 16px)",
              padding: "28px",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 200ms ease, box-shadow 200ms ease",
            }}
          >
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md, 10px)",
                background: "#fee2e2",
                color: "#ef4444",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "18px",
              }}
            >
              <MapPin size={22} />
            </div>
            <h3
              style={{ fontSize: "18px", fontWeight: 700, marginBottom: "8px" }}
            >
              Coordinate Shift Inversion
            </h3>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                lineHeight: 1.6,
              }}
            >
              Full mathematical reverse Newton-Raphson iteration for mainland
              China. Drop pins freely on Amap or Baidu and store canonical
              unobfuscated WGS-84 coordinates.
            </p>
          </div>

          {/* Card 6 */}
          <div
            style={{
              background: "var(--bg-surface, #ffffff)",
              border: "1px solid var(--border-color, #e2e8f0)",
              borderRadius: "var(--radius-lg, 16px)",
              padding: "28px",
              boxShadow: "var(--shadow-sm)",
              transition: "transform 200ms ease, box-shadow 200ms ease",
            }}
          >
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-md, 10px)",
                background: "#e0f2fe",
                color: "#0284c7",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "18px",
              }}
            >
              <ShieldCheck size={22} />
            </div>
            <h3
              style={{ fontSize: "18px", fontWeight: 700, marginBottom: "8px" }}
            >
              W3C Tracing & Security
            </h3>
            <p
              style={{
                fontSize: "14px",
                color: "var(--text-secondary)",
                lineHeight: 1.6,
              }}
            >
              Strict distributed tracing headers, SHA-256 geocache table for
              polite OSM Nominatim compliance, and isolated Shadow DOM UI for
              the browser extension.
            </p>
          </div>
        </div>
      </section>

      {/* Interactive Feature Deep Dive Tabs */}
      <section
        style={{
          padding: "60px 24px 80px 24px",
          background: "var(--bg-surface, #ffffff)",
          borderTop: "1px solid var(--border-color, #e2e8f0)",
          borderBottom: "1px solid var(--border-color, #e2e8f0)",
        }}
      >
        <div style={{ maxWidth: "1060px", margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: "36px" }}>
            <h2
              style={{ fontSize: "28px", fontWeight: 800, marginBottom: "8px" }}
            >
              Experience the Workflow
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "15px" }}>
              Explore how Vistarae simplifies capturing, organizing, and
              exploring destinations.
            </p>

            {/* Tab Buttons */}
            <div
              style={{
                display: "inline-flex",
                gap: "8px",
                padding: "4px",
                borderRadius: "var(--radius-md, 10px)",
                background: "var(--bg-hover, #f1f5f9)",
                marginTop: "20px",
              }}
            >
              <button
                type="button"
                onClick={() => setActiveTab("capture")}
                style={{
                  padding: "8px 18px",
                  borderRadius: "var(--radius-sm, 6px)",
                  background:
                    activeTab === "capture"
                      ? "var(--bg-surface, #ffffff)"
                      : "transparent",
                  color:
                    activeTab === "capture"
                      ? "var(--accent, #2563eb)"
                      : "var(--text-secondary)",
                  fontWeight: 700,
                  fontSize: "13px",
                  boxShadow:
                    activeTab === "capture" ? "var(--shadow-sm)" : "none",
                }}
              >
                Browser Capture
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("maps")}
                style={{
                  padding: "8px 18px",
                  borderRadius: "var(--radius-sm, 6px)",
                  background:
                    activeTab === "maps"
                      ? "var(--bg-surface, #ffffff)"
                      : "transparent",
                  color:
                    activeTab === "maps"
                      ? "var(--accent, #2563eb)"
                      : "var(--text-secondary)",
                  fontWeight: 700,
                  fontSize: "13px",
                  boxShadow: activeTab === "maps" ? "var(--shadow-sm)" : "none",
                }}
              >
                Vector Basemaps
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("triage")}
                style={{
                  padding: "8px 18px",
                  borderRadius: "var(--radius-sm, 6px)",
                  background:
                    activeTab === "triage"
                      ? "var(--bg-surface, #ffffff)"
                      : "transparent",
                  color:
                    activeTab === "triage"
                      ? "var(--accent, #2563eb)"
                      : "var(--text-secondary)",
                  fontWeight: 700,
                  fontSize: "13px",
                  boxShadow:
                    activeTab === "triage" ? "var(--shadow-sm)" : "none",
                }}
              >
                Intelligent Ingestion
              </button>
            </div>
          </div>

          {/* Tab Content 1: Browser Capture */}
          {activeTab === "capture" && (
            <div
              className="slide-up"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: "32px",
                alignItems: "center",
                padding: "32px",
                borderRadius: "var(--radius-lg, 16px)",
                background: "var(--bg-primary, #f8fafc)",
                border: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    color: "var(--accent)",
                    textTransform: "uppercase",
                  }}
                >
                  Chrome Manifest V3 Extension
                </span>
                <h3
                  style={{
                    fontSize: "22px",
                    fontWeight: 800,
                    margin: "8px 0 12px 0",
                  }}
                >
                  Capture Directly From Travel Articles
                </h3>
                <p
                  style={{
                    fontSize: "14px",
                    color: "var(--text-secondary)",
                    lineHeight: 1.6,
                    marginBottom: "16px",
                  }}
                >
                  Highlight any paragraph, location recommendation, or trail
                  name on blogs like Lonely Planet or Atlas Obscura. Press{" "}
                  <code>Ctrl+Shift+S</code> to open the lightweight shadow DOM
                  capture overlay.
                </p>
                <ul
                  style={{
                    listStyle: "none",
                    padding: 0,
                    margin: 0,
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                    fontSize: "13px",
                  }}
                >
                  <li
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <CheckCircle2 size={16} color="#10b981" /> No style
                    contamination on host pages
                  </li>
                  <li
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <CheckCircle2 size={16} color="#10b981" /> Auto-extracts
                    source URL and page metadata
                  </li>
                  <li
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <CheckCircle2 size={16} color="#10b981" /> Instantly syncs
                    to your personal cloud POI list
                  </li>
                </ul>
              </div>

              <div
                style={{
                  background: "var(--bg-surface, #ffffff)",
                  borderRadius: "var(--radius-md, 10px)",
                  padding: "20px",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  boxShadow: "var(--shadow-md)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "12px",
                    fontSize: "12px",
                    color: "var(--text-muted)",
                  }}
                >
                  <Bookmark size={14} color="var(--accent)" />
                  <span>Captured Highlight Preview</span>
                </div>
                <blockquote
                  style={{
                    fontSize: "13px",
                    fontStyle: "italic",
                    color: "var(--text-primary)",
                    borderLeft: "3px solid var(--accent, #2563eb)",
                    paddingLeft: "12px",
                    marginBottom: "14px",
                  }}
                >
                  &quot;Take the funicular up to Sacré-Cœur at twilight for the
                  most breathtaking panoramic view of the entire city of
                  Paris.&quot;
                </blockquote>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                    paddingTop: "10px",
                    borderTop: "1px solid var(--border-color, #e2e8f0)",
                  }}
                >
                  <span>
                    Resolved: <strong>Sacré-Cœur Basilica</strong>
                  </span>
                  <span style={{ color: "#10b981", fontWeight: 700 }}>
                    Geocoded (48.8867° N)
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Tab Content 2: Vector Basemaps */}
          {activeTab === "maps" && (
            <div
              className="slide-up"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: "32px",
                alignItems: "center",
                padding: "32px",
                borderRadius: "var(--radius-lg, 16px)",
                background: "var(--bg-primary, #f8fafc)",
                border: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    color: "var(--accent)",
                    textTransform: "uppercase",
                  }}
                >
                  High-Definition Vector Tiles
                </span>
                <h3
                  style={{
                    fontSize: "22px",
                    fontWeight: 800,
                    margin: "8px 0 12px 0",
                  }}
                >
                  True English Landmark Labels Worldwide
                </h3>
                <p
                  style={{
                    fontSize: "14px",
                    color: "var(--text-secondary)",
                    lineHeight: 1.6,
                    marginBottom: "16px",
                  }}
                >
                  Standard raster tiles bake local foreign characters into PNG
                  pixels. With OpenFreeMap vector integration, MapLibre GL
                  renders crisp English names like &quot;Eiffel Tower&quot; or
                  &quot;Forbidden City&quot; while preserving 60 FPS
                  performance.
                </p>
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <span
                    style={{
                      fontSize: "12px",
                      padding: "4px 10px",
                      borderRadius: "var(--radius-full)",
                      background: "var(--accent-light)",
                      color: "var(--accent)",
                      fontWeight: 600,
                    }}
                  >
                    OpenFreeMap Liberty
                  </span>
                  <span
                    style={{
                      fontSize: "12px",
                      padding: "4px 10px",
                      borderRadius: "var(--radius-full)",
                      background: "var(--bg-hover)",
                      color: "var(--text-secondary)",
                      fontWeight: 600,
                    }}
                  >
                    Google Hybrid
                  </span>
                  <span
                    style={{
                      fontSize: "12px",
                      padding: "4px 10px",
                      borderRadius: "var(--radius-full)",
                      background: "var(--bg-hover)",
                      color: "var(--text-secondary)",
                      fontWeight: 600,
                    }}
                  >
                    ESRI Satellite
                  </span>
                </div>
              </div>

              <div
                style={{
                  background: "var(--bg-surface, #ffffff)",
                  borderRadius: "var(--radius-md, 10px)",
                  padding: "20px",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  boxShadow: "var(--shadow-md)",
                }}
              >
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    marginBottom: "12px",
                  }}
                >
                  Tile Label Comparison
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    fontSize: "13px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "var(--bg-hover)",
                    }}
                  >
                    <span style={{ color: "var(--text-muted)" }}>
                      Standard Raster OSM:
                    </span>
                    <span style={{ fontWeight: 600 }}>
                      Tour Eiffel (French only)
                    </span>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "#eff6ff",
                      border: "1px solid #bfdbfe",
                    }}
                  >
                    <span style={{ color: "var(--accent)", fontWeight: 700 }}>
                      OpenFreeMap Vector:
                    </span>
                    <span style={{ fontWeight: 700, color: "var(--accent)" }}>
                      Eiffel Tower (English)
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab Content 3: Smart Triage */}
          {activeTab === "triage" && (
            <div
              className="slide-up"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: "32px",
                alignItems: "center",
                padding: "32px",
                borderRadius: "var(--radius-lg, 16px)",
                background: "var(--bg-primary, #f8fafc)",
                border: "1px solid var(--border-color, #e2e8f0)",
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    color: "var(--accent)",
                    textTransform: "uppercase",
                  }}
                >
                  Resilient Data Pipeline
                </span>
                <h3
                  style={{
                    fontSize: "22px",
                    fontWeight: 800,
                    margin: "8px 0 12px 0",
                  }}
                >
                  Bulk CSV Ingest with Intelligent Triage
                </h3>
                <p
                  style={{
                    fontSize: "14px",
                    color: "var(--text-secondary)",
                    lineHeight: 1.6,
                    marginBottom: "16px",
                  }}
                >
                  Import spreadsheets from Google Sheets, Tripadvisor, or Apple
                  Maps exports. Our async processing pipeline handles multi-site
                  rows by letting you split or disambiguate locations offline
                  via local IndexedDB.
                </p>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    fontSize: "13px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <CheckCircle2 size={16} color="#10b981" /> Header
                    auto-detection for Lat, Long, Name, Tags
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <CheckCircle2 size={16} color="#10b981" /> Trigram
                    similarity & spatial deduplication
                  </div>
                </div>
              </div>

              <div
                style={{
                  background: "var(--bg-surface, #ffffff)",
                  borderRadius: "var(--radius-md, 10px)",
                  padding: "20px",
                  border: "1px solid var(--border-color, #e2e8f0)",
                  boxShadow: "var(--shadow-md)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "10px",
                  }}
                >
                  <span style={{ fontSize: "12px", fontWeight: 700 }}>
                    Triage Disambiguation
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      background: "#fef3c7",
                      color: "#b45309",
                      fontWeight: 700,
                    }}
                  >
                    Split Required
                  </span>
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                    padding: "8px 10px",
                    background: "var(--bg-hover)",
                    borderRadius: "6px",
                    marginBottom: "10px",
                  }}
                >
                  Row 4: &quot;Kyoto: Fushimi Inari &amp; Kinkaku-ji&quot;
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "8px",
                    fontSize: "11px",
                    fontWeight: 600,
                  }}
                >
                  <div
                    style={{
                      flex: 1,
                      padding: "6px",
                      border: "1px dashed var(--border-color)",
                      borderRadius: "4px",
                      textAlign: "center",
                    }}
                  >
                    📍 Fushimi Inari Shrine
                  </div>
                  <div
                    style={{
                      flex: 1,
                      padding: "6px",
                      border: "1px dashed var(--border-color)",
                      borderRadius: "4px",
                      textAlign: "center",
                    }}
                  >
                    📍 Kinkaku-ji Golden Pavilion
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section
        style={{
          padding: "80px 24px",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <div
          style={{
            maxWidth: "960px",
            width: "100%",
            borderRadius: "var(--radius-lg, 24px)",
            padding: "56px 36px",
            textAlign: "center",
            background:
              "linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #4338ca 100%)",
            color: "#ffffff",
            boxShadow:
              "0 20px 40px -10px rgba(37, 99, 235, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.1)",
          }}
        >
          <h2
            style={{
              fontSize: "clamp(26px, 4vw, 40px)",
              fontWeight: 900,
              color: "#ffffff",
              marginBottom: "16px",
              letterSpacing: "-0.02em",
            }}
          >
            Start Mapping Your Travel Dreams Today
          </h2>
          <p
            style={{
              fontSize: "17px",
              color: "rgba(255, 255, 255, 0.85)",
              maxWidth: "600px",
              margin: "0 auto 36px auto",
              lineHeight: 1.6,
            }}
          >
            Sign up in 30 seconds to unlock the full POI Explorer, multi-layer
            basemaps, and Chrome Extension synchronization.
          </p>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "14px",
              justifyContent: "center",
            }}
          >
            <button
              type="button"
              onClick={onNavigateSignUp}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "14px 30px",
                borderRadius: "var(--radius-md, 10px)",
                background: "#ffffff",
                color: "#1e3a8a",
                fontSize: "15px",
                fontWeight: 800,
                boxShadow: "0 10px 20px rgba(0, 0, 0, 0.15)",
              }}
            >
              <UserPlus size={18} />
              <span>Create Free Account</span>
            </button>

            <button
              type="button"
              onClick={onNavigateLogin}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "14px 26px",
                borderRadius: "var(--radius-md, 10px)",
                background: "rgba(255, 255, 255, 0.15)",
                border: "1px solid rgba(255, 255, 255, 0.3)",
                color: "#ffffff",
                fontSize: "15px",
                fontWeight: 700,
              }}
            >
              <LogIn size={18} />
              <span>Sign In</span>
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer
        style={{
          marginTop: "auto",
          padding: "36px 24px",
          background: "var(--bg-surface, #ffffff)",
          borderTop: "1px solid var(--border-color, #e2e8f0)",
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "16px",
          fontSize: "13px",
          color: "var(--text-secondary)",
          maxWidth: "1140px",
          width: "100%",
          margin: "0 auto",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "18px" }}>🧭</span>
          <span style={{ fontWeight: 800, color: "var(--text-primary)" }}>
            Vistarae
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            © 2026 Vistarae. All rights reserved.
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
          <button
            type="button"
            onClick={onNavigateLogin}
            style={{
              color: "var(--text-secondary)",
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={onNavigateSignUp}
            style={{
              color: "var(--text-secondary)",
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            Sign Up
          </button>
          {onNavigateTerms && (
            <button
              type="button"
              onClick={onNavigateTerms}
              style={{
                color: "var(--text-secondary)",
                fontWeight: 600,
                fontSize: "13px",
              }}
            >
              Terms of Service
            </button>
          )}
        </div>
      </footer>
    </div>
  );
};
