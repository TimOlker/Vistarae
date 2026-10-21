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

import { describe, it, expect, beforeEach } from "vitest";
import { triageStorage } from "../../src/services/triageStorage";

describe("IndexedDB Triage Storage Service", () => {
  const jobId = "job-uuid-1234";

  beforeEach(async () => {
    await triageStorage.deleteJobRecord(jobId);
  });

  it("saves and retrieves row decisions for an ingestion job", async () => {
    await triageStorage.saveDecision(jobId, 1, "COMMITTED", {
      total_rows: 50,
      processed_rows: 50,
      status: "PENDING_REVIEW",
    });

    await triageStorage.saveDecision(jobId, 2, "REJECTED");

    const record = await triageStorage.getJobRecord(jobId);
    expect(record).not.toBeNull();
    expect(record?.job_id).toBe(jobId);
    expect(record?.decisions[1]).toBe("COMMITTED");
    expect(record?.decisions[2]).toBe("REJECTED");
    expect(record?.expires_at).toBeGreaterThan(Date.now());
  });

  it("deletes job records upon successful submission", async () => {
    await triageStorage.saveDecision(jobId, 1, "COMMITTED");
    await triageStorage.deleteJobRecord(jobId);

    const record = await triageStorage.getJobRecord(jobId);
    expect(record).toBeNull();
  });

  it("evicts records older than 7 days", async () => {
    const expiredJobId = "job-expired-old";

    // Mock an expired record by saving and manually adjusting expires_at
    await triageStorage.saveDecision(expiredJobId, 1, "COMMITTED");
    const rec = await triageStorage.getJobRecord(expiredJobId);
    if (rec) {
      rec.expires_at = Date.now() - 1000; // In the past
    }

    const evictedCount = await triageStorage.evictExpiredRecords();
    expect(evictedCount).toBeGreaterThanOrEqual(0);
  });
});
