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
import { Modal } from "../common/Modal";
import { Sparkles, Compass, ArrowRight } from "lucide-react";

export interface TravelStyleOnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSetUp?: () => void;
}

export const TravelStyleOnboardingModal: React.FC<TravelStyleOnboardingModalProps> = ({
  isOpen,
  onClose,
  onSetUp,
}) => {
  if (!isOpen) return null;

  const handleSetUpClick = () => {
    if (typeof window !== "undefined") {
      sessionStorage.setItem("vistarae_travel_style_dismissed", "true");
    }
    if (onSetUp) {
      onSetUp();
    } else if (typeof window !== "undefined") {
      window.location.href = "/profile#travel-style";
    }
    onClose();
  };

  const handleRemindLaterClick = () => {
    if (typeof window !== "undefined") {
      sessionStorage.setItem("vistarae_travel_style_dismissed", "true");
    }
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleRemindLaterClick}
      title="Personalize Your Travel Experience"
      maxWidth="520px"
    >
      <div data-testid="travel-style-onboarding-modal" style={{ padding: "8px 0" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            background: "linear-gradient(135deg, rgba(37,99,235,0.12) 0%, rgba(147,51,234,0.12) 100%)",
            color: "var(--accent, #2563eb)",
            margin: "0 auto 16px auto",
          }}
        >
          <Sparkles size={28} />
        </div>

        <h3
          style={{
            fontSize: "18px",
            fontWeight: 700,
            textAlign: "center",
            margin: "0 0 10px 0",
            color: "var(--text-primary, #0f172a)",
          }}
        >
          Make Vistarae Truly Yours
        </h3>

        <p
          style={{
            fontSize: "14px",
            lineHeight: 1.6,
            color: "var(--text-secondary, #475569)",
            textAlign: "center",
            margin: "0 0 20px 0",
          }}
        >
          Tell Vistarae what you look for in travel — whether you're a culinary traveler
          hunting artisan bakeries, a history buff, or an outdoor enthusiast.
          Our AI engine automatically tailors your web captures with personalized
          descriptions, reasons to visit, and visit pace recommendations.
        </p>

        <div
          style={{
            background: "var(--bg-muted, #f8fafc)",
            border: "1px solid var(--border-color, #e2e8f0)",
            borderRadius: "var(--radius-md, 8px)",
            padding: "12px 16px",
            marginBottom: "24px",
            fontSize: "13px",
            color: "var(--text-secondary, #64748b)",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <Compass size={20} color="var(--accent, #2563eb)" style={{ flexShrink: 0 }} />
          <span>Takes less than 1 minute and can be updated anytime in your profile.</span>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          <button
            type="button"
            data-testid="travel-style-modal-setup-btn"
            onClick={handleSetUpClick}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              width: "100%",
              padding: "12px 18px",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              border: "none",
              borderRadius: "var(--radius-md, 8px)",
              fontSize: "14px",
              fontWeight: 600,
              cursor: "pointer",
              transition: "background 0.15s ease",
            }}
          >
            <span>Set Up Travel Style</span>
            <ArrowRight size={16} />
          </button>

          <button
            type="button"
            data-testid="travel-style-modal-remind-btn"
            onClick={handleRemindLaterClick}
            style={{
              width: "100%",
              padding: "10px 18px",
              background: "transparent",
              color: "var(--text-secondary, #64748b)",
              border: "1px solid var(--border-color, #cbd5e1)",
              borderRadius: "var(--radius-md, 8px)",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Remind Me Later
          </button>
        </div>
      </div>
    </Modal>
  );
};
