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

import { openDB, type IDBPDatabase } from "idb";

export type TriageDecision = "COMMITTED" | "REJECTED";

export interface StagedTriageJob {
  job_id: string;
  total_rows: number;
  processed_rows: number;
  status: string;
  decisions: Record<number, TriageDecision>; // indexed by row_number
  last_updated: number;
  expires_at: number; // 7 days from last update
}

const DB_NAME = "vistarae_ingest_db";
const STORE_NAME = "triage_jobs";
const DB_VERSION = 1;
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

async function getDB(): Promise<IDBPDatabase | null> {
  if (typeof indexedDB === "undefined") {
    return null;
  }
  try {
    return await openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "job_id" });
        }
      },
    });
  } catch (err) {
    console.warn(
      "IndexedDB unavailable (possibly strict private mode), falling back to in-memory:",
      err,
    );
    return null;
  }
}

// In-memory fallback if IndexedDB is disabled in private browsing
const memoryStore: Record<string, StagedTriageJob> = {};

export const triageStorage = {
  /**
   * Saves or updates a duplicate review decision for a specific row in an ingestion job.
   */
  async saveDecision(
    jobId: string,
    rowNumber: number,
    decision: TriageDecision,
    meta?: Partial<StagedTriageJob>,
  ): Promise<void> {
    const now = Date.now();
    const expiresAt = now + SEVEN_DAYS_MS;

    const db = await getDB();
    if (db) {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const existing = (await store.get(jobId)) as StagedTriageJob | undefined;

      const record: StagedTriageJob = {
        job_id: jobId,
        total_rows: meta?.total_rows ?? existing?.total_rows ?? 0,
        processed_rows: meta?.processed_rows ?? existing?.processed_rows ?? 0,
        status: meta?.status ?? existing?.status ?? "PENDING",
        decisions: {
          ...(existing?.decisions || {}),
          [rowNumber]: decision,
        },
        last_updated: now,
        expires_at: expiresAt,
      };

      await store.put(record);
      await tx.done;
    } else {
      const existing = memoryStore[jobId];
      memoryStore[jobId] = {
        job_id: jobId,
        total_rows: meta?.total_rows ?? existing?.total_rows ?? 0,
        processed_rows: meta?.processed_rows ?? existing?.processed_rows ?? 0,
        status: meta?.status ?? existing?.status ?? "PENDING",
        decisions: {
          ...(existing?.decisions || {}),
          [rowNumber]: decision,
        },
        last_updated: now,
        expires_at: expiresAt,
      };
    }
  },

  /**
   * Retrieves all staged triage decisions for a given job.
   */
  async getJobRecord(jobId: string): Promise<StagedTriageJob | null> {
    const db = await getDB();
    if (db) {
      const record = (await db.get(STORE_NAME, jobId)) as
        StagedTriageJob | undefined;
      return record || null;
    }
    return memoryStore[jobId] || null;
  },

  /**
   * Deletes a job record upon completion or successful triage submission.
   */
  async deleteJobRecord(jobId: string): Promise<void> {
    const db = await getDB();
    if (db) {
      await db.delete(STORE_NAME, jobId);
    }
    delete memoryStore[jobId];
  },

  /**
   * Opportunistically evicts records older than 7 days on application load.
   */
  async evictExpiredRecords(): Promise<number> {
    const now = Date.now();
    let evictedCount = 0;

    const db = await getDB();
    if (db) {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      const allRecords = (await store.getAll()) as StagedTriageJob[];

      for (const rec of allRecords) {
        if (rec.expires_at <= now) {
          await store.delete(rec.job_id);
          evictedCount++;
        }
      }
      await tx.done;
    } else {
      for (const [id, rec] of Object.entries(memoryStore)) {
        if (rec.expires_at <= now) {
          delete memoryStore[id];
          evictedCount++;
        }
      }
    }

    return evictedCount;
  },
};
