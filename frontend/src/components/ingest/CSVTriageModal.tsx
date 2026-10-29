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

import React, { useEffect, useState } from "react";
import { Modal } from "../common/Modal";
import { ingestApi, type CandidateItem } from "../../services/ingestApi";
import { useToast } from "../../context/ToastContext";
import {
  X,
  ArrowRight,
  MapPin,
  Folder,
  Calendar,
  AlertTriangle,
  Compass,
} from "lucide-react";

export interface ExistingPOIMarker {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
}

export interface CSVTriageModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onProceedToPhase2?: () => void;
  onTriageComplete?: () => void;
  existingPOIs?: ExistingPOIMarker[];
}

export const CSVTriageModal: React.FC<CSVTriageModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onProceedToPhase2,
  onTriageComplete,
  existingPOIs = [],
}) => {
  const { showToast } = useToast();

  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen || !jobId) return;

    const loadData = async () => {
      setIsLoading(true);
      try {
        const res = await ingestApi.getJobCandidates(jobId, "phase_1_triage");
        setCandidates(res.candidates || []);
        if (res.candidates && res.candidates.length > 0) {
          setSelectedCandidateId(res.candidates[0].id);
        }
      } catch (err: any) {
        showToast(err?.message || "Failed to load staged candidates", "error");
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [isOpen, jobId, showToast]);

  const handleDispositionChange = async (
    candidateId: string,
    newDisp: "accept" | "ignore" | "update_existing" | "sublocation",
  ) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidateId ? { ...c, user_disposition: newDisp } : c,
      ),
    );

    if (jobId) {
      try {
        await ingestApi.updateCandidate(jobId, candidateId, {
          user_disposition: newDisp,
        });
      } catch (err: any) {
        showToast(`Failed to save disposition: ${err.message}`, "error");
      }
    }
  };

  const handleUpdateCoordinatesToggle = async (
    candidateId: string,
    updateCoords: boolean,
  ) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidateId ? { ...c, update_coordinates: updateCoords } : c,
      ),
    );

    if (jobId) {
      try {
        await ingestApi.updateCandidate(jobId, candidateId, {
          update_coordinates: updateCoords,
        });
      } catch (err: any) {
        showToast(`Failed to toggle coordinate update: ${err.message}`, "error");
      }
    }
  };

  const handleMarkerClick = async (poi: ExistingPOIMarker) => {
    if (!selectedCandidateId) return;

    const selected = candidates.find((c) => c.id === selectedCandidateId);
    if (!selected) return;

    const disp = selected.user_disposition || selected.recommended_disposition;
    if (disp === "sublocation") {
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === selectedCandidateId
            ? { ...c, parent_poi_id: poi.id, parent_poi_name: poi.name }
            : c,
        ),
      );

      if (jobId) {
        try {
          await ingestApi.updateCandidate(jobId, selectedCandidateId, {
            parent_poi_id: poi.id,
          });
          showToast(`Linked '${selected.poi_name}' to parent '${poi.name}'`, "success");
        } catch (err: any) {
          showToast(`Failed to link parent POI: ${err.message}`, "error");
        }
      }
    }
  };

  const handleCancel = async () => {
    if (!jobId) {
      onClose();
      return;
    }
    setIsSubmitting(true);
    try {
      await ingestApi.cancelPhase1(jobId);
      showToast("Phase 1 triage cancelled. Staged records purged.", "info");
      onClose();
    } catch (err: any) {
      showToast(`Cancellation failed: ${err.message}`, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleProceed = async () => {
    if (!jobId) return;
    setIsSubmitting(true);
    try {
      const res = await ingestApi.proceedPhase1(jobId);
      showToast(
        `Advanced ${res.advanced_count} POIs to Phase 2 (${res.ignored_count} ignored)`,
        "success",
      );
      (onProceedToPhase2 || onTriageComplete)?.();
    } catch (err: any) {
      showToast(`Failed to proceed to Phase 2: ${err.message}`, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectedCandidate = candidates.find((c) => c.id === selectedCandidateId);

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleCancel}
      title="Phase 1: Validation & Triage"
      maxWidth="1100px"
    >
      <div className="flex flex-col h-[75vh]" data-testid="phase1-triage-modal">
        {isLoading ? (
          <div className="flex items-center justify-center flex-1">
            <span className="text-gray-500">Loading staged candidates...</span>
          </div>
        ) : (
          <>
            {/* Top explanation bar */}
            <div className="p-3 mb-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Compass className="w-5 h-5 text-blue-600 shrink-0" />
                <span>
                  Review candidate dispositions, edit coordinates or addresses, and click existing POI markers on the map to set parent POIs for sublocations.
                </span>
              </div>
              <div className="text-xs font-semibold px-2 py-1 bg-blue-200 rounded text-blue-900">
                {candidates.length} Candidate(s)
              </div>
            </div>

            {/* Split view: Table (Left 60%) + Map / Parent selector (Right 40%) */}
            <div className="flex flex-1 gap-4 overflow-hidden">
              {/* Candidates Table */}
              <div className="flex-1 overflow-auto border border-gray-200 rounded-lg">
                <table className="w-full text-left text-sm" data-testid="candidates-table">
                  <thead className="bg-gray-100 text-gray-700 sticky top-0 border-b border-gray-200 z-10">
                    <tr>
                      <th className="p-3">POI Name</th>
                      <th className="p-3">Disposition</th>
                      <th className="p-3">Confidence</th>
                      <th className="p-3">Location / Hierarchy</th>
                      <th className="p-3">Directory / Dates</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {candidates.map((cand) => {
                      const isSelected = cand.id === selectedCandidateId;
                      const disp = cand.user_disposition || cand.recommended_disposition;
                      const isUpdate = disp === "update_existing";
                      const isSublocation = disp === "sublocation";

                      return (
                        <tr
                          key={cand.id}
                          onClick={() => setSelectedCandidateId(cand.id)}
                          className={`cursor-pointer transition-colors ${
                            isSelected ? "bg-blue-50/70" : "hover:bg-gray-50"
                          }`}
                          data-testid={`candidate-row-${cand.id}`}
                        >
                          <td className="p-3 font-medium text-gray-900">
                            <div>{cand.poi_name}</div>
                            {cand.street_address && (
                              <div className="text-xs text-gray-500 truncate max-w-xs">
                                {cand.street_address}, {cand.city || ""}
                              </div>
                            )}
                          </td>
                          <td className="p-3">
                            <select
                              value={disp}
                              onChange={(e) =>
                                handleDispositionChange(
                                  cand.id,
                                  e.target.value as any,
                                )
                              }
                              className="px-2 py-1 text-xs border border-gray-300 rounded bg-white font-medium focus:ring-1 focus:ring-blue-500"
                              data-testid={`disposition-select-${cand.id}`}
                            >
                              <option value="accept">Accept</option>
                              <option value="sublocation">Sublocation</option>
                              <option value="update_existing">Update Existing POI</option>
                              <option value="ignore">Ignore</option>
                            </select>
                            {isUpdate && (
                              <label className="flex items-center gap-1.5 mt-1.5 text-xs text-amber-700 cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={cand.update_coordinates}
                                  onChange={(e) =>
                                    handleUpdateCoordinatesToggle(
                                      cand.id,
                                      e.target.checked,
                                    )
                                  }
                                  data-testid={`update-coords-toggle-${cand.id}`}
                                  className="rounded border-amber-400 text-amber-600 focus:ring-amber-500 h-3.5 w-3.5"
                                />
                                <span>Update Coordinates</span>
                              </label>
                            )}
                          </td>
                          <td className="p-3">
                            <span
                              className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
                                cand.confidence_score >= 70
                                  ? "bg-green-100 text-green-800"
                                  : cand.confidence_score >= 40
                                  ? "bg-yellow-100 text-yellow-800"
                                  : "bg-red-100 text-red-800"
                              }`}
                            >
                              {cand.confidence_score}%
                            </span>
                          </td>
                          <td className="p-3 text-xs text-gray-600">
                            {cand.latitude && cand.longitude ? (
                              <div className="flex items-center gap-1">
                                <MapPin className="w-3.5 h-3.5 text-blue-500" />
                                <span>
                                  {Number(cand.latitude).toFixed(4)},{" "}
                                  {Number(cand.longitude).toFixed(4)}
                                </span>
                              </div>
                            ) : (
                              <span className="text-red-500 font-medium">Missing Coordinates</span>
                            )}
                            {isSublocation && (
                              <div className="mt-1 font-medium text-purple-700">
                                {cand.parent_poi_name ? (
                                  <span>Parent: {cand.parent_poi_name}</span>
                                ) : (
                                  <span className="text-purple-500 italic">
                                    Click map marker to set parent
                                  </span>
                                )}
                              </div>
                            )}
                          </td>
                          <td className="p-3 text-xs text-gray-500">
                            <div className="flex items-center gap-1 truncate max-w-xs">
                              <Folder className="w-3 h-3 text-gray-400 shrink-0" />
                              <span className="truncate">{cand.photo_directory}</span>
                            </div>
                            {cand.dates_visited && cand.dates_visited.length > 0 && (
                              <div className="flex items-center gap-1 mt-0.5 text-gray-400">
                                <Calendar className="w-3 h-3 shrink-0" />
                                <span>{cand.dates_visited.join(", ")}</span>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Map & Parent Selector View (Right Pane) */}
              <div
                className="w-80 border border-gray-200 rounded-lg p-3 bg-gray-50 flex flex-col justify-between"
                data-testid="interactive-map-panel"
              >
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-2 flex items-center gap-1">
                    <MapPin className="w-4 h-4 text-gray-500" /> Map Coordinates & Hierarchy
                  </h4>

                  {selectedCandidate ? (
                    <div className="bg-white p-3 rounded border border-gray-200 text-xs mb-3 space-y-1.5">
                      <div className="font-semibold text-gray-900">{selectedCandidate.poi_name}</div>
                      <div className="text-gray-600">
                        Coordinates:{" "}
                        {selectedCandidate.latitude
                          ? `${Number(selectedCandidate.latitude).toFixed(5)}, ${Number(
                              selectedCandidate.longitude,
                            ).toFixed(5)}`
                          : "None"}
                      </div>
                      {selectedCandidate.parent_poi_name && (
                        <div className="text-purple-700 font-medium">
                          Parent POI: {selectedCandidate.parent_poi_name}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400 italic mb-3">No candidate selected.</div>
                  )}

                  <div className="text-xs font-semibold text-gray-700 mb-1.5">
                    Existing User POIs (click to link as parent):
                  </div>
                  <div
                    className="space-y-1.5 max-h-56 overflow-y-auto"
                    data-testid="existing-poi-list"
                  >
                    {existingPOIs.length === 0 ? (
                      <div className="text-xs text-gray-400 italic">No proximate POIs found.</div>
                    ) : (
                      existingPOIs.map((poi) => (
                        <button
                          key={poi.id}
                          type="button"
                          onClick={() => handleMarkerClick(poi)}
                          data-testid={`poi-marker-${poi.id}`}
                          className="w-full text-left p-2 rounded border border-gray-200 bg-white hover:bg-purple-50 hover:border-purple-300 text-xs flex items-center justify-between transition-colors"
                        >
                          <span className="font-medium text-gray-800">{poi.name}</span>
                          <span className="text-[10px] text-gray-400">
                            {poi.latitude.toFixed(2)}, {poi.longitude.toFixed(2)}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </div>

                <div className="text-[11px] text-gray-500 border-t border-gray-200 pt-2">
                  <div className="flex items-center gap-1 text-gray-600">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                    <span>Ignored rows will not advance to Phase 2.</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between pt-4 border-t border-gray-200 mt-3">
              <button
                type="button"
                onClick={handleCancel}
                disabled={isSubmitting}
                className="px-4 py-2 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 flex items-center gap-1.5"
                data-testid="cancel-triage-button"
              >
                <X className="w-4 h-4 text-gray-500" /> Cancel Import
              </button>

              <button
                type="button"
                onClick={handleProceed}
                disabled={isSubmitting || candidates.length === 0}
                className="px-5 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2 shadow-sm"
                data-testid="proceed-phase2-button"
              >
                {isSubmitting ? (
                  <span>Processing...</span>
                ) : (
                  <>
                    <span>Proceed to Phase 2</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};
