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

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CSVUploadModal } from "../../components/ingest/CSVUploadModal";
import { ToastProvider } from "../../context/ToastContext";
import { apiFetch } from "../../services/api";

vi.mock("../../services/api", () => ({
  apiFetch: vi.fn(),
}));

describe("CSVUploadModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders upload modal with target list input and datalist", async () => {
    (apiFetch as any).mockImplementation(async (url: string) => {
      if (url === "/api/lists") {
        return [
          { id: "list-1", title: "London Trip" },
          { id: "list-2", title: "Summer 2025" },
        ];
      }
      if (url === "/api/ingest/active-session") {
        return { has_active_session: false, job_id: null };
      }
      return {};
    });

    render(
      <ToastProvider>
        <CSVUploadModal
          isOpen={true}
          onClose={vi.fn()}
          onJobCreated={vi.fn()}
        />
      </ToastProvider>,
    );

    expect(screen.getByText("Import Travel Points (CSV)")).toBeInTheDocument();
    expect(screen.getByLabelText(/assign to list/i)).toBeInTheDocument();

    await waitFor(() => {
      const options = document.querySelectorAll("#existing-lists-datalist option");
      expect(options.length).toBe(2);
      expect((options[0] as HTMLOptionElement).value).toBe("London Trip");
      expect((options[1] as HTMLOptionElement).value).toBe("Summer 2025");
    });
  });

  it("submits target_list_name in formData when specified", async () => {
    (apiFetch as any).mockImplementation(async (url: string) => {
      if (url === "/api/lists") {
        return [{ id: "list-1", title: "London Trip" }];
      }
      if (url === "/api/ingest/active-session") {
        return { has_active_session: false, job_id: null };
      }
      if (url === "/api/ingest/upload" || url === "/api/v1/ingest/upload-flexible") {
        return { job_id: "job-new-123", status: "QUEUED" };
      }
      return {};
    });

    const onJobCreated = vi.fn();
    const onClose = vi.fn();

    render(
      <ToastProvider>
        <CSVUploadModal
          isOpen={true}
          onClose={onClose}
          onJobCreated={onJobCreated}
        />
      </ToastProvider>,
    );

    // Enter target list name
    const listInput = screen.getByTestId("target-list-input");
    fireEvent.change(listInput, { target: { value: "Japan Vacation" } });

    // Select file
    const file = new File(["name,latitude,longitude\nTokyo Tower,35.6586,139.7454"], "test.csv", {
      type: "text/csv",
    });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Click Start Ingestion
    const startBtn = screen.getByRole("button", { name: /start ingestion/i });
    fireEvent.click(startBtn);

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api(\/v1)?\/ingest\/(upload|upload-flexible)/),
        expect.objectContaining({
          method: "POST",
          body: expect.any(FormData),
        }),
      );
    });

    const callArgs = (apiFetch as any).mock.calls.find(
      (c: any[]) => c[0] === "/api/ingest/upload" || c[0] === "/api/v1/ingest/upload-flexible",
    );
    const formData = callArgs[1].body as FormData;
    expect(formData.get("target_list_name")).toBe("Japan Vacation");
    expect(onJobCreated).toHaveBeenCalledWith("job-new-123");
    expect(onClose).toHaveBeenCalled();
  });

  it("displays resume banner card when an active session is detected and resumes", async () => {
    (apiFetch as any).mockImplementation(async (url: string) => {
      if (url === "/api/lists") return [];
      if (url === "/api/ingest/active-session") {
        return {
          has_active_session: true,
          job_id: "job-active-456",
          phase_state: "phase_1_triage",
          total_candidates: 12,
          created_at: "2026-10-29T20:00:00Z",
          target_list_name: "Favorites",
        };
      }
      return {};
    });

    const onResumeJob = vi.fn();
    const onClose = vi.fn();

    render(
      <ToastProvider>
        <CSVUploadModal
          isOpen={true}
          onClose={onClose}
          onJobCreated={vi.fn()}
          onResumeJob={onResumeJob}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("active-session-card")).toBeInTheDocument();
      expect(screen.getByText(/In-Progress Import Detected/i)).toBeInTheDocument();
      expect(screen.getByText(/12/)).toBeInTheDocument();
    });

    const resumeBtn = screen.getByTestId("resume-import-button");
    fireEvent.click(resumeBtn);

    expect(onResumeJob).toHaveBeenCalledWith("job-active-456", "phase_1_triage");
    expect(onClose).toHaveBeenCalled();
  });

  it("warns user with overwrite confirmation modal if active session exists and user attempts new upload", async () => {
    (apiFetch as any).mockImplementation(async (url: string) => {
      if (url === "/api/lists") return [];
      if (url === "/api/ingest/active-session") {
        return {
          has_active_session: true,
          job_id: "job-active-789",
          phase_state: "phase_2_enriched",
          total_candidates: 25,
          created_at: "2026-10-29T20:00:00Z",
        };
      }
      if (url === "/api/ingest/upload" || url === "/api/v1/ingest/upload-flexible") {
        return { job_id: "job-new-999", status: "QUEUED" };
      }
      return {};
    });

    const onJobCreated = vi.fn();

    render(
      <ToastProvider>
        <CSVUploadModal
          isOpen={true}
          onClose={vi.fn()}
          onJobCreated={onJobCreated}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("active-session-card")).toBeInTheDocument();
    });

    // Select file
    const file = new File(["name,lat,lng\nParis,48.8,2.3"], "new.csv", {
      type: "text/csv",
    });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Click Start Ingestion
    const startBtn = screen.getByRole("button", { name: /start ingestion/i });
    fireEvent.click(startBtn);

    // Overwrite warning modal should appear
    await waitFor(() => {
      expect(screen.getByTestId("overwrite-warning-modal")).toBeInTheDocument();
      expect(
        screen.getByText(/Previous Import Progress Will Be Wiped Out/i),
      ).toBeInTheDocument();
    });

    // Confirm overwrite
    const confirmBtn = screen.getByTestId("confirm-overwrite-button");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(onJobCreated).toHaveBeenCalledWith("job-new-999");
    });
  });

  it("opens column mapping modal when CSV lacks name column, allowing user to map and submit", async () => {
    (apiFetch as any).mockImplementation(async (url: string) => {
      if (url === "/api/lists") return [];
      if (url === "/api/ingest/active-session") {
        return { has_active_session: false, job_id: null };
      }
      if (url === "/api/ingest/upload") {
        return { job_id: "job-mapped-123" };
      }
      return {};
    });

    const onJobCreated = vi.fn();
    const onClose = vi.fn();

    render(
      <ToastProvider>
        <CSVUploadModal
          isOpen={true}
          onClose={onClose}
          onJobCreated={onJobCreated}
        />
      </ToastProvider>,
    );

    // Select file with unmapped headers (missing "name")
    const csvContent = "Site,Locality,Notes\nMachu Picchu,Cusco,Inca Citadel";
    const file = new File([csvContent], "peru_sites.csv", { type: "text/csv" });
    file.text = async () => csvContent;

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText("peru_sites.csv")).toBeInTheDocument();
      expect(screen.getByTestId("btn-open-mapping-preview")).toBeInTheDocument();
    });

    // Click Start Ingestion -> should trigger column mapping modal because name is missing
    const startBtn = screen.getByRole("button", { name: /start ingestion/i });
    fireEvent.click(startBtn);

    await waitFor(() => {
      expect(screen.getByTestId("column-mapping-modal")).toBeInTheDocument();
      expect(screen.getByText("Map Travel Point Columns")).toBeInTheDocument();
      expect(screen.getByTestId("select-mapping-Site")).toBeInTheDocument();
    });

    // Site is auto-suggested to poi_name; click Apply Mapping & Import
    const applyBtn = screen.getByTestId("apply-column-mapping-btn");
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/ingest/upload",
        expect.objectContaining({
          method: "POST",
          body: expect.any(FormData),
        }),
      );
      expect(onJobCreated).toHaveBeenCalledWith("job-mapped-123");
    });
  });

  it("displays 'Map Columns & Continue' in error banner when upload fails with Invalid CSV Header", async () => {
    (apiFetch as any).mockImplementation(async (url: string) => {
      if (url === "/api/lists") return [];
      if (url === "/api/ingest/active-session") {
        return { has_active_session: false, job_id: null };
      }
      if (url === "/api/ingest/upload") {
        const err: any = new Error("CSV header validation failed: missing required column(s) ['name'].");
        err.problem = {
          title: "Invalid CSV Header",
          detail: "CSV header validation failed: missing required column(s) ['name'].",
          found_headers: ["wonders", "locality", "notes"],
          missing_headers: ["name"],
        };
        throw err;
      }
      return {};
    });

    render(
      <ToastProvider>
        <CSVUploadModal
          isOpen={true}
          onClose={vi.fn()}
          onJobCreated={vi.fn()}
        />
      </ToastProvider>,
    );

    const csvContent = "wonders,locality,notes\nTaj Mahal,Agra,Mausoleum";
    const file = new File([csvContent], "monuments.csv", { type: "text/csv" });
    file.text = async () => csvContent;

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [file] } });

    const startBtn = screen.getByRole("button", { name: /start ingestion/i });
    fireEvent.click(startBtn);

    // Error banner should display Map Columns & Continue button
    await waitFor(() => {
      expect(screen.getByText("Invalid CSV Header")).toBeInTheDocument();
      expect(screen.getByTestId("open-column-mapping-btn")).toBeInTheDocument();
    });

    // Clicking button opens the Column Mapping modal
    const openMappingBtn = screen.getByTestId("open-column-mapping-btn");
    fireEvent.click(openMappingBtn);

    await waitFor(() => {
      expect(screen.getByTestId("column-mapping-modal")).toBeInTheDocument();
    });
  });

  it("clears target_list_name when Clear button is clicked", async () => {
    render(
      <ToastProvider>
        <CSVUploadModal
          isOpen={true}
          onClose={vi.fn()}
          onJobCreated={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Import Travel Points (CSV)")).toBeInTheDocument();
    });

    const listInput = screen.getByTestId("target-list-input") as HTMLInputElement;
    const clearBtn = screen.getByTestId("clear-target-list-button");

    // Initially empty, button is disabled
    expect(listInput.value).toBe("");
    expect(clearBtn).toBeDisabled();

    // Type a list name
    fireEvent.change(listInput, { target: { value: "My Trip List" } });
    expect(listInput.value).toBe("My Trip List");
    expect(clearBtn).not.toBeDisabled();

    // Click Clear
    fireEvent.click(clearBtn);
    expect(listInput.value).toBe("");
    expect(clearBtn).toBeDisabled();
  });

  it("does not close when clicking the backdrop outside of the window", async () => {
    const onClose = vi.fn();
    render(
      <ToastProvider>
        <CSVUploadModal
          isOpen={true}
          onClose={onClose}
          onJobCreated={vi.fn()}
        />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Import Travel Points (CSV)")).toBeInTheDocument();
    });

    const backdrop = document.querySelector(".modal-backdrop") as HTMLElement;
    expect(backdrop).toBeInTheDocument();

    fireEvent.click(backdrop);
    expect(onClose).not.toHaveBeenCalled();
  });
});

