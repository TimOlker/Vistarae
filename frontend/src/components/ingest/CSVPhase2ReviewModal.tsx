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
  Save,
  X,
  MapPin,
  CheckCircle,
  EyeOff,
  Sparkles,
} from "lucide-react";

export interface CSVPhase2ReviewModalProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onCommitComplete: () => void;
}

export const CSVPhase2ReviewModal: React.FC<CSVPhase2ReviewModalProps> = ({
  jobId,
  isOpen,
  onClose,
  onCommitComplete,
}) => {
  const { showToast } = useToast();

  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Edit drawer / modal state
  const [editingCandidate, setEditingCandidate] = useState<CandidateItem | null>(null);
  const [editForm, setEditForm] = useState({
    poi_name: "",
    description: "",
    reason_to_visit: "",
    tags: "",
    street_address: "",
    city: "",
    update_coordinates: false,
  });

  useEffect(() => {
    if (!isOpen || !jobId) return;

    const loadData = async () => {
      setIsLoading(true);
      try {
        const res = await ingestApi.getJobCandidates(jobId, "phase_2_enriched");
        const active = (res.candidates || []).filter(
          (c) => (c.user_disposition || c.recommended_disposition) !== "ignore",
        );
        setCandidates(active);
        if (active.length > 0) {
          setSelectedCandidateId(active[0].id);
        }
      } catch (err: any) {
        showToast(err?.message || "Failed to load enriched candidates", "error");
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [isOpen, jobId, showToast]);

  const handleToggleSkip = async (cand: CandidateItem) => {
    const nextSkipped = !cand.is_skipped;
    setCandidates((prev) =>
      prev.map((c) => (c.id === cand.id ? { ...c, is_skipped: nextSkipped } : c)),
    );

    if (jobId) {
      try {
        await ingestApi.updateCandidate(jobId, cand.id, {
          is_skipped: nextSkipped,
        });
        showToast(
          nextSkipped ? `Skipped '${cand.poi_name}'` : `Unskipped '${cand.poi_name}'`,
          "info",
        );
      } catch (err: any) {
        showToast(`Failed to toggle skip: ${err.message}`, "error");
      }
    }
  };

  const openEditModal = (cand: CandidateItem) => {
    setEditingCandidate(cand);
    setEditForm({
      poi_name: cand.poi_name,
      description: cand.description || "",
      reason_to_visit: cand.reason_to_visit || "",
      tags: (cand.tags || []).join(", "),
      street_address: cand.street_address || "",
      city: cand.city || "",
      update_coordinates: cand.update_coordinates,
    });
  };

  const handleSaveEdit = async () => {
    if (!editingCandidate || !jobId) return;

    const updatedTags = editForm.tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    try {
      const updated = await ingestApi.updateCandidate(jobId, editingCandidate.id, {
        poi_name: editForm.poi_name,
        description: editForm.description,
        reason_to_visit: editForm.reason_to_visit,
        tags: updatedTags,
        street_address: editForm.street_address,
        city: editForm.city,
        update_coordinates: editForm.update_coordinates,
      });

      setCandidates((prev) =>
        prev.map((c) => (c.id === editingCandidate.id ? { ...c, ...updated } : c)),
      );
      setEditingCandidate(null);
      showToast(`Updated '${editForm.poi_name}'`, "success");
    } catch (err: any) {
      showToast(`Failed to save changes: ${err.message}`, "error");
    }
  };

  const handleSaveToDB = async () => {
    if (!jobId) return;
    setIsSubmitting(true);
    try {
      const res = await ingestApi.commitPhase2(jobId);
      showToast(
        `Saved ${res.committed_count} POIs to your map! (${res.created_pois.length} created, ${res.merged_pois.length} merged)`,
        "success",
      );
      onCommitComplete();
    } catch (err: any) {
      showToast(`Database commit failed: ${err.message}`, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (!jobId) {
      onClose();
      return;
    }
    setIsSubmitting(true);
    try {
      await ingestApi.cancelPhase2(jobId);
      showToast("Phase 2 review cancelled; staged records purged.", "info");
      onClose();
    } catch (err: any) {
      showToast(`Cancellation failed: ${err.message}`, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectedCandidate = candidates.find((c) => c.id === selectedCandidateId);
  const activeCount = candidates.filter((c) => !c.is_skipped).length;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleCancel}
      title="Phase 2: AI Enrichment Review & Commit"
      maxWidth="1100px"
    >
      <div className="flex flex-col h-[75vh]" data-testid="phase2-review-modal">
        {isLoading ? (
          <div className="flex items-center justify-center flex-1">
            <span className="text-gray-500">Loading enriched candidates...</span>
          </div>
        ) : (
          <>
            {/* Top banner */}
            <div className="p-3 mb-3 bg-purple-50 border border-purple-200 rounded-lg text-sm text-purple-900 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-600 shrink-0" />
                <span>
                  AI synthesized descriptions and customized reasons to visit based on your travel profile. Review, edit, or skip before saving to your database.
                </span>
              </div>
              <div className="text-xs font-semibold px-2 py-1 bg-purple-200 rounded text-purple-950">
                {activeCount} Ready to Commit
              </div>
            </div>

            {/* Split view */}
            <div className="flex flex-1 gap-4 overflow-hidden">
              {/* Enriched Candidates Table */}
              <div className="flex-1 overflow-auto border border-gray-200 rounded-lg">
                <table className="w-full text-left text-sm" data-testid="enriched-candidates-table">
                  <thead className="bg-gray-100 text-gray-700 sticky top-0 border-b border-gray-200 z-10">
                    <tr>
                      <th className="p-3">POI & Address</th>
                      <th className="p-3">AI Description</th>
                      <th className="p-3">Personalized Reason to Visit</th>
                      <th className="p-3">Tags</th>
                      <th className="p-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {candidates.map((cand) => {
                      const isSelected = cand.id === selectedCandidateId;

                      return (
                        <tr
                          key={cand.id}
                          onClick={() => setSelectedCandidateId(cand.id)}
                          className={`cursor-pointer transition-colors ${
                            cand.is_skipped
                              ? "opacity-40 bg-gray-50"
                              : isSelected
                              ? "bg-purple-50/70"
                              : "hover:bg-gray-50"
                          }`}
                          data-testid={`enriched-row-${cand.id}`}
                        >
                          <td className="p-3 font-medium text-gray-900 w-44">
                            <div className="flex items-center gap-1.5">
                              {cand.is_skipped ? (
                                <EyeOff className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                              ) : (
                                <CheckCircle className="w-3.5 h-3.5 text-green-500 shrink-0" />
                              )}
                              <span className="truncate">{cand.poi_name}</span>
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5 truncate">
                              {cand.city || cand.country || "No locality"}
                            </div>
                          </td>
                          <td className="p-3 text-xs text-gray-700 max-w-xs">
                            <p className="line-clamp-3">
                              {cand.description || (
                                <span className="italic text-gray-400">No description</span>
                              )}
                            </p>
                          </td>
                          <td className="p-3 text-xs text-gray-700 max-w-xs">
                            <p className="line-clamp-3">
                              {cand.reason_to_visit || (
                                <span className="italic text-gray-400">No rationale</span>
                              )}
                            </p>
                          </td>
                          <td className="p-3 text-xs text-gray-600">
                            <div className="flex flex-wrap gap-1">
                              {(cand.tags || []).slice(0, 3).map((tag, i) => (
                                <span
                                  key={i}
                                  className="px-1.5 py-0.5 bg-gray-100 rounded text-[10px] text-gray-700"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="p-3 text-right space-x-2 whitespace-nowrap">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleToggleSkip(cand);
                              }}
                              className={`text-xs px-2 py-1 rounded border font-medium ${
                                cand.is_skipped
                                  ? "border-green-300 text-green-700 hover:bg-green-50"
                                  : "border-gray-300 text-gray-600 hover:bg-gray-100"
                              }`}
                              data-testid={`skip-toggle-${cand.id}`}
                            >
                              {cand.is_skipped ? "Include" : "Skip"}
                            </button>

                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                openEditModal(cand);
                              }}
                              className="text-xs text-purple-600 hover:text-purple-800 underline font-medium"
                              data-testid={`edit-poi-btn-${cand.id}`}
                            >
                              Edit
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Synchronized Map / Detail View (Right Pane) */}
              <div
                className="w-80 border border-gray-200 rounded-lg p-3 bg-gray-50 flex flex-col justify-between"
                data-testid="phase2-map-panel"
              >
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-2 flex items-center gap-1">
                    <MapPin className="w-4 h-4 text-purple-600" /> Active Selection Details
                  </h4>

                  {selectedCandidate ? (
                    <div className="bg-white p-3 rounded border border-gray-200 text-xs space-y-2">
                      <div className="font-bold text-gray-900 text-sm">
                        {selectedCandidate.poi_name}
                      </div>
                      <div className="text-gray-600">
                        Coordinates:{" "}
                        {selectedCandidate.latitude
                          ? `${Number(selectedCandidate.latitude).toFixed(5)}, ${Number(
                              selectedCandidate.longitude,
                            ).toFixed(5)}`
                          : "None"}
                      </div>
                      {selectedCandidate.street_address && (
                        <div className="text-gray-500">
                          {selectedCandidate.street_address}, {selectedCandidate.city}
                        </div>
                      )}
                      <div className="pt-2 border-t border-gray-100">
                        <span className="font-semibold text-gray-700">Reason to Visit:</span>
                        <p className="text-gray-600 mt-1 italic">
                          "{selectedCandidate.reason_to_visit}"
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400 italic">No candidate selected.</div>
                  )}
                </div>

                <div className="text-[11px] text-gray-500 border-t border-gray-200 pt-2">
                  <span>Skipped items will be discarded and not added to your map.</span>
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
                data-testid="cancel-phase2-button"
              >
                <X className="w-4 h-4 text-gray-500" /> Cancel Import
              </button>

              <button
                type="button"
                onClick={handleSaveToDB}
                disabled={isSubmitting || activeCount === 0}
                className="px-5 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-700 disabled:opacity-50 flex items-center gap-2 shadow-sm"
                data-testid="save-to-db-button"
              >
                {isSubmitting ? (
                  <span>Saving to DB...</span>
                ) : (
                  <>
                    <Save className="w-4 h-4" />
                    <span>Save {activeCount} POI(s) to DB</span>
                  </>
                )}
              </button>
            </div>
          </>
        )}
      </div>

      {/* Edit Drawer Modal */}
      {editingCandidate && (
        <Modal
          isOpen={true}
          onClose={() => setEditingCandidate(null)}
          title={`Edit ${editingCandidate.poi_name}`}
          maxWidth="600px"
        >
          <div className="space-y-3 p-1 text-sm" data-testid="poi-edit-drawer">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                POI Name
              </label>
              <input
                type="text"
                value={editForm.poi_name}
                onChange={(e) => setEditForm({ ...editForm, poi_name: e.target.value })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                data-testid="edit-poi-name-input"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Description
              </label>
              <textarea
                rows={3}
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                data-testid="edit-poi-description-input"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Reason to Visit
              </label>
              <textarea
                rows={3}
                value={editForm.reason_to_visit}
                onChange={(e) => setEditForm({ ...editForm, reason_to_visit: e.target.value })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                data-testid="edit-poi-reason-input"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Tags (comma-separated)
              </label>
              <input
                type="text"
                value={editForm.tags}
                onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                data-testid="edit-poi-tags-input"
              />
            </div>

            {editingCandidate.recommended_disposition === "update_existing" && (
              <label className="flex items-center gap-2 text-xs text-amber-800 font-medium cursor-pointer pt-1">
                <input
                  type="checkbox"
                  checked={editForm.update_coordinates}
                  onChange={(e) =>
                    setEditForm({ ...editForm, update_coordinates: e.target.checked })
                  }
                  data-testid="edit-update-coordinates-toggle"
                  className="rounded border-amber-400 text-amber-600 focus:ring-amber-500 h-4 w-4"
                />
                <span>Update Existing POI Coordinates</span>
              </label>
            )}

            <div className="flex justify-end gap-2 pt-3 border-t border-gray-200 mt-4">
              <button
                type="button"
                onClick={() => setEditingCandidate(null)}
                className="px-4 py-1.5 border border-gray-300 rounded text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                className="px-4 py-1.5 bg-purple-600 text-white rounded text-sm font-medium hover:bg-purple-700"
                data-testid="save-edit-button"
              >
                Apply Changes
              </button>
            </div>
          </div>
        </Modal>
      )}
    </Modal>
  );
};

