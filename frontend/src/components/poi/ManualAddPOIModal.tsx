// Copyright (c) 2026 Vistarae. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState, useEffect } from "react";
import { Modal } from "../common/Modal";
import {
  extractPhotoEXIF,
  cleanupPhotoPreview,
  type ExtractedPhotoMetadata,
} from "../../utils/exifReader";
import { useToast } from "../../context/ToastContext";
import type { POIMapFeature, VisitState } from "../../types/map";
import {
  Upload,
  MapPin,
  Compass,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";

interface ManualAddPOIModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddPOI: (poi: POIMapFeature) => void;
  onStartPickOnMap: () => void;
  pickedCoords?: { lng: number; lat: number } | null;
}

export const ManualAddPOIModal: React.FC<ManualAddPOIModalProps> = ({
  isOpen,
  onClose,
  onAddPOI,
  onStartPickOnMap,
  pickedCoords,
}) => {
  const { showToast } = useToast();

  const [name, setName] = useState("");
  const [latitude, setLatitude] = useState<string>("");
  const [longitude, setLongitude] = useState<string>("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [visitState, setVisitState] = useState<VisitState>("not_visited");
  const [rating, setRating] = useState<number>(0);
  const [tagsInput, setTagsInput] = useState("");

  const [photoMetadata, setPhotoMetadata] =
    useState<ExtractedPhotoMetadata | null>(null);
  const [isParsingPhoto, setIsParsingPhoto] = useState(false);

  // Sync coords from map picker if user picked a point
  useEffect(() => {
    if (pickedCoords) {
      setLongitude(pickedCoords.lng.toFixed(6));
      setLatitude(pickedCoords.lat.toFixed(6));
    }
  }, [pickedCoords]);

  // Clean up Blob preview on close or photo replacement
  useEffect(() => {
    return () => {
      if (photoMetadata?.previewUrl) {
        cleanupPhotoPreview(photoMetadata.previewUrl);
      }
    };
  }, [photoMetadata]);

  const handlePhotoSelect = async (file: File) => {
    if (photoMetadata?.previewUrl) {
      cleanupPhotoPreview(photoMetadata.previewUrl);
    }

    setIsParsingPhoto(true);
    try {
      const meta = await extractPhotoEXIF(file);
      setPhotoMetadata(meta);

      if (meta.hasGps && meta.latitude !== null && meta.longitude !== null) {
        setLatitude(meta.latitude.toFixed(6));
        setLongitude(meta.longitude.toFixed(6));
        showToast(
          "GPS coordinates extracted from photo in browser memory!",
          "success",
        );
      } else {
        showToast(
          "No GPS data found in this photo. Please pick on map or use current location.",
          "info",
        );
      }

      if (!name && meta.fileName) {
        const cleanName = meta.fileName
          .replace(/\.[^/.]+$/, "")
          .replace(/[-_]/g, " ");
        setName(cleanName);
      }
    } catch {
      showToast("Could not parse photo EXIF metadata", "warning");
    } finally {
      setIsParsingPhoto(false);
    }
  };

  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      showToast("Geolocation is not supported by your browser", "warning");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(pos.coords.latitude.toFixed(6));
        setLongitude(pos.coords.longitude.toFixed(6));
        showToast("Current location coordinates set!", "success");
      },
      (err) => {
        showToast(`Geolocation access denied: ${err.message}`, "warning");
      },
      { timeout: 10000, enableHighAccuracy: true },
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const lat = parseFloat(latitude);
    const lng = parseFloat(longitude);

    if (isNaN(lat) || isNaN(lng)) {
      showToast("Valid latitude and longitude are required.", "warning");
      return;
    }

    const newPOI: POIMapFeature = {
      id: crypto.randomUUID(),
      name,
      canonical_lat: lat,
      canonical_lng: lng,
      render_lat: lat,
      render_lng: lng,
      visit_state: visitState,
      rating: rating > 0 ? rating : null,
      city: city || undefined,
      address: address || undefined,
      tags: tagsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };

    onAddPOI(newPOI);
    showToast(`Added POI "${name}"!`, "success");
    handleClose();
  };

  const handleClose = () => {
    if (photoMetadata?.previewUrl) {
      cleanupPhotoPreview(photoMetadata.previewUrl);
    }
    setPhotoMetadata(null);
    setName("");
    setLatitude("");
    setLongitude("");
    setCity("");
    setAddress("");
    setTagsInput("");
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Add Point of Interest"
      maxWidth="560px"
    >
      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", flexDirection: "column", gap: "16px" }}
      >
        {/* Photo Dropzone */}
        <div
          style={{
            border: "2px dashed var(--border-color, #cbd5e1)",
            borderRadius: "var(--radius-md, 10px)",
            padding: "16px",
            textAlign: "center",
            background: "var(--bg-hover, #f8fafc)",
            cursor: "pointer",
            position: "relative",
          }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
              handlePhotoSelect(e.dataTransfer.files[0]);
            }
          }}
        >
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handlePhotoSelect(e.target.files[0]);
              }
            }}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              opacity: 0,
              cursor: "pointer",
            }}
          />

          {photoMetadata?.previewUrl ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                textAlign: "left",
              }}
            >
              <img
                src={photoMetadata.previewUrl}
                alt="Preview"
                style={{
                  width: "64px",
                  height: "64px",
                  objectFit: "cover",
                  borderRadius: "8px",
                }}
              />
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: "13px", fontWeight: 600 }}>
                  {photoMetadata.fileName}
                </p>
                <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {(photoMetadata.fileSizeBytes / 1024).toFixed(1)} KB • Memory
                  parsed only (Zero AWS egress)
                </p>
                {photoMetadata.hasGps ? (
                  <span
                    style={{
                      fontSize: "11px",
                      color: "var(--success)",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <CheckCircle2 size={13} /> GPS Extracted
                  </span>
                ) : (
                  <span
                    style={{
                      fontSize: "11px",
                      color: "var(--warning)",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <AlertCircle size={13} /> No GPS metadata found
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <Upload size={24} color="var(--accent, #2563eb)" />
              <p style={{ fontSize: "13px", fontWeight: 600 }}>
                {isParsingPhoto
                  ? "Parsing photo in memory..."
                  : "Drop a photo to auto-fill location from EXIF"}
              </p>
              <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                Supports JPEG, PNG, WebP, HEIC/HEIF • Zero cloud bandwidth
              </p>
            </div>
          )}
        </div>

        {/* Name input */}
        <div>
          <label
            style={{
              fontSize: "12px",
              fontWeight: 700,
              display: "block",
              marginBottom: "6px",
            }}
          >
            POI Name *
          </label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Scenic Overlook"
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "var(--radius-md, 8px)",
              border: "1px solid var(--border-color, #e2e8f0)",
              fontSize: "13px",
            }}
          />
        </div>

        {/* Coordinates with location helpers */}
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "6px",
            }}
          >
            <label style={{ fontSize: "12px", fontWeight: 700 }}>
              Coordinates (Canonical WGS-84) *
            </label>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                type="button"
                onClick={handleUseCurrentLocation}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  fontSize: "11px",
                  color: "var(--accent, #2563eb)",
                  fontWeight: 600,
                }}
              >
                <Compass size={13} />
                <span>Current Location</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  onStartPickOnMap();
                  onClose();
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  fontSize: "11px",
                  color: "var(--accent, #2563eb)",
                  fontWeight: 600,
                }}
              >
                <MapPin size={13} />
                <span>Pick on Map</span>
              </button>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "10px",
            }}
          >
            <input
              type="number"
              step="any"
              required
              value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
              placeholder="Latitude (-90 to 90)"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            />
            <input
              type="number"
              step="any"
              required
              value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
              placeholder="Longitude (-180 to 180)"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            />
          </div>
        </div>

        {/* City and Address */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "10px",
          }}
        >
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              City
            </label>
            <input
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Kyoto"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            />
          </div>
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Address / Notes
            </label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Street or trailhead"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            />
          </div>
        </div>

        {/* Visit Status & Rating */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "10px",
          }}
        >
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Visit Status
            </label>
            <select
              value={visitState}
              onChange={(e) => setVisitState(e.target.value as VisitState)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            >
              <option value="not_visited">Not Visited</option>
              <option value="visited_return">Visited (Would Return)</option>
              <option value="visited_do_not_return">
                Visited (Will Not Return)
              </option>
            </select>
          </div>
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 700,
                display: "block",
                marginBottom: "6px",
              }}
            >
              Rating (0-5 stars)
            </label>
            <input
              type="number"
              min={0}
              max={5}
              value={rating}
              onChange={(e) => setRating(parseInt(e.target.value, 10) || 0)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md, 8px)",
                border: "1px solid var(--border-color, #e2e8f0)",
                fontSize: "13px",
              }}
            />
          </div>
        </div>

        {/* Tags */}
        <div>
          <label
            style={{
              fontSize: "12px",
              fontWeight: 700,
              display: "block",
              marginBottom: "6px",
            }}
          >
            Tags (comma-separated)
          </label>
          <input
            type="text"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="temple, garden, viewpoint"
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "var(--radius-md, 8px)",
              border: "1px solid var(--border-color, #e2e8f0)",
              fontSize: "13px",
            }}
          />
        </div>

        {/* Action Buttons */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "8px",
            marginTop: "12px",
          }}
        >
          <button
            type="button"
            onClick={handleClose}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--bg-hover, #f1f5f9)",
              color: "var(--text-secondary)",
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            Cancel
          </button>
          <button
            type="submit"
            style={{
              padding: "8px 20px",
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent, #2563eb)",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            Save POI
          </button>
        </div>
      </form>
    </Modal>
  );
};
