# Frontend Interfaces & Contract Specifications: Phase 4 — Single-Page Application (SPA) & Interactive POI Frontend

**Feature Identifier**: `004-spa-poi-frontend`  
**Date**: 2026-10-20  
**Status**: Completed  
**Spec Reference**: [specs/004-spa-poi-frontend/spec.md](file:///d:/Coding/Vistarae/specs/004-spa-poi-frontend/spec.md)  
**OpenAPI Reference**: [openapi.json](file:///d:/Coding/Vistarae/openapi.json)

---

## 1. OpenAPI TypeScript Contract Synchronization

Per Constitution Principle 5, the authoritative backend OpenAPI contract (`./openapi.json`) generates TypeScript definitions via:

```bash
npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts
```

### 1.1 Consumed OpenAPI Endpoint Endpoints

| Route Path                          |  Method  | Operation ID                                    | Consuming Frontend Component / Service                     |
| :---------------------------------- | :------: | :---------------------------------------------- | :--------------------------------------------------------- |
| `/api/auth/register`                |  `POST`  | `register_api_auth_register_post`               | `RegisterForm.tsx`                                         |
| `/api/auth/confirm-signup`          |  `POST`  | `confirm_signup_api_auth_confirm_signup_post`   | `ConfirmCodeForm.tsx`                                      |
| `/api/auth/login`                   |  `POST`  | `login_api_auth_login_post`                     | `LoginForm.tsx`                                            |
| `/api/auth/forgot-password`         |  `POST`  | `forgot_password_api_auth_forgot_password_post` | `ForgotPasswordForm.tsx`                                   |
| `/api/auth/reset-password`          |  `POST`  | `reset_password_api_auth_reset_password_post`   | `ResetPasswordForm.tsx`                                    |
| `/api/auth/logout`                  |  `POST`  | `logout_api_auth_logout_post`                   | `Navbar.tsx` (Logout button)                               |
| `/api/users/me`                     |  `GET`   | `get_me`                                        | `ProfilePage.tsx`                                          |
| `/api/users/me`                     | `PATCH`  | `update_me`                                     | `ProfilePage.tsx`                                          |
| `/api/users/me`                     | `DELETE` | `delete_me`                                     | `DeleteAccountModal.tsx`                                   |
| `/api/users/me/preferences`         |  `GET`   | `get_preferences`                               | `PreferencesContext.tsx`                                   |
| `/api/users/me/preferences/ui`      | `PATCH`  | `patch_ui_preferences`                          | `AccountPreferencesTab.tsx`, `ThemeSwitcher.tsx`           |
| `/api/users/me/preferences/poi`     | `PATCH`  | `patch_poi_preferences`                         | `POIPreferencesTab.tsx`, `MapLayerSwitcher.tsx`            |
| `/api/users/me/preferences/planner` | `PATCH`  | `patch_planner_preferences`                     | `PlannerPreferencesTab.tsx`                                |
| `/api/pois`                         |  `GET`   | `list_pois`                                     | `MapView.tsx`, `POITable.tsx` (supports `bbox`, `q`, etc.) |
| `/api/pois`                         |  `POST`  | `create_poi`                                    | `ManualAddPOIModal.tsx`                                    |
| `/api/pois/{id}`                    |  `GET`   | `get_poi`                                       | `POIDetailDrawer.tsx`                                      |
| `/api/pois/{id}`                    | `PATCH`  | `update_poi`                                    | `POIDetailDrawer.tsx`                                      |
| `/api/pois/{id}`                    | `DELETE` | `delete_poi`                                    | `POITable.tsx`, `POIDetailDrawer.tsx`                      |
| `/api/ingest/upload`                |  `POST`  | `upload_csv`                                    | `CSVUploadModal.tsx`                                       |
| `/api/ingest/jobs/{job_id}`         |  `GET`   | `get_job_progress`                              | `CSVProgressModal.tsx`, `CSVTriageModal.tsx`               |
| `/api/ingest/jobs/{job_id}/triage`  |  `POST`  | `submit_duplicate_triage`                       | `CSVTriageModal.tsx`                                       |
| `/api/admin/users`                  |  `GET`   | `admin_list_users`                              | `AdminDashboard.tsx`                                       |
| `/api/admin/users/{id}/tier`        | `PATCH`  | `admin_update_tier`                             | `AdminDashboard.tsx`                                       |
| `/api/admin/users/{id}/status`      | `PATCH`  | `admin_update_status`                           | `AdminDashboard.tsx`                                       |
| `/api/admin/metrics`                |  `GET`   | `admin_get_metrics`                             | `AdminDashboard.tsx`                                       |
| `/api/admin/controls`               |  `GET`   | `admin_get_controls`                            | `AdminDashboard.tsx`                                       |

---

## 2. HTTP Transport & Telemetry Contract

Every HTTP request dispatched by the frontend `apiClient` enforces the following header protocol:

```text
Request Headers:
  Authorization: Bearer <cognito_jwt_token>
  Content-Type: application/json (or multipart/form-data for CSV upload)
  traceparent: 00-{trace_id}-{client_span_id}-01 (W3C Distributed Tracing)
  X-Source: web-client
  X-Destination: backend
  Idempotency-Key: <uuidv4> (Mandatory on mutating POST/PATCH/DELETE)

Local Mocking Headers (when VITE_APP_ENV === 'local'):
  X-Mock-User-Id: <user_uuid>
  X-Mock-User-Tier: LOW | HIGH | ADMIN
```

### 2.1 RFC 7807 / RFC 9457 Error Response Schema

```typescript
export interface ProblemDetails {
  type: string; // Absolute URI reference identifying problem type
  title: string; // Short, human-readable summary
  status: number; // HTTP status code (e.g. 400, 401, 403, 404, 409, 413, 422, 429, 500)
  detail: string; // Human-readable explanation specific to this occurrence
  instance?: string; // URI reference that identifies the specific occurrence of the problem
  invalid_params?: Array<{
    // Included on 400/422 validation failures
    name: string; // Property or parameter path (e.g. "email", "recommended_duration_hours")
    reason: string; // Specific constraint violation explanation
  }>;
}
```

---

## 3. Two-Way Coordinate Transform Module Contract

Module Path: `frontend/src/utils/coordinates.ts`

### 3.1 Interface Signatures

```typescript
export interface CoordinatePoint {
  lng: number; // Longitude in degrees (-180.0 to 180.0)
  lat: number; // Latitude in degrees (-90.0 to 90.0)
}

export interface BoundingBox {
  minLng: number;
  minLat: number;
  maxLng: number;
  maxLat: number;
}

/**
 * Returns true if the coordinate point falls strictly inside the China geographic bounding box:
 * 73.66°E <= lng <= 135.05°E and 18.16°N <= lat <= 53.55°N.
 */
export function isInChinaBBox(lng: number, lat: number): boolean;

/**
 * Converts canonical WGS-84 coordinates to GCJ-02 (Mars Coordinates) for AutoNavi/Amap rendering.
 * Returns unaltered coordinates if point is outside China bounding box.
 */
export function wgs84_to_gcj02(lng: number, lat: number): CoordinatePoint;

/**
 * Converts GCJ-02 coordinates back to canonical WGS-84 using Newton's numerical iteration method.
 * Iterates until difference < 0.000001° (sub-meter ground accuracy, <= 30 iterations).
 * Returns unaltered coordinates if point is outside China bounding box.
 */
export function gcj02_to_wgs84(lng: number, lat: number): CoordinatePoint;

/**
 * Converts canonical WGS-84 coordinates to Baidu BD-09 coordinates.
 */
export function wgs84_to_bd09(lng: number, lat: number): CoordinatePoint;

/**
 * Converts Baidu BD-09 coordinates back to canonical WGS-84 coordinates.
 */
export function bd09_to_wgs84(lng: number, lat: number): CoordinatePoint;
```

### 3.2 Numerical Precision Test Vectors & Invariants

```text
Test Fixture 1: Beijing Tiananmen Square
  Canonical WGS-84 Input:   [116.397458, 39.909187]
  Transformed GCJ-02:       [116.403694, 39.910543]  (approx ~500m offset)
  Reverse gcj02_to_wgs84:   [116.397458, 39.909187]  (|diff| < 1e-6 degrees)

Test Fixture 2: Shanghai Tower
  Canonical WGS-84 Input:   [121.505676, 31.233519]
  Transformed GCJ-02:       [121.510167, 31.231502]
  Reverse gcj02_to_wgs84:   [121.505676, 31.233519]  (|diff| < 1e-6 degrees)

Test Fixture 3: International Out-of-Bounds (Paris Eiffel Tower)
  Canonical WGS-84 Input:   [2.2945, 48.8584]
  Transformed GCJ-02:       [2.2945, 48.8584]        (No-op pass-through)
  Reverse gcj02_to_wgs84:   [2.2945, 48.8584]        (No-op pass-through)
```

---

## 4. Client Photo EXIF Reader Contract

Module Path: `frontend/src/utils/exifReader.ts`

### 4.1 Interface Signatures

```typescript
export interface ExtractedPhotoMetadata {
  fileName: string;
  fileSizeBytes: number;
  mimeType:
    | "image/jpeg"
    | "image/webp"
    | "image/png"
    | "image/heic"
    | "image/heif";
  hasGps: boolean;
  latitude: number | null; // Canonical WGS-84 (-90.0 to 90.0)
  longitude: number | null; // Canonical WGS-84 (-180.0 to 180.0)
  capturedAt: string | null; // ISO 8601 string ("YYYY-MM-DDTHH:mm:ssZ")
  orientation: number | null; // EXIF orientation integer 1..8
  previewUrl: string; // Ephemeral Blob URL generated via URL.createObjectURL(file)
}

/**
 * Extracts GPS and timestamp metadata entirely within client memory.
 * Emits zero outbound network bytes to external services.
 * Caller MUST invoke cleanupPhotoPreview(metadata.previewUrl) upon component unmount.
 */
export function extractPhotoEXIF(file: File): Promise<ExtractedPhotoMetadata>;

/**
 * Revokes ephemeral Blob URL to prevent memory leaks in the browser.
 */
export function cleanupPhotoPreview(previewUrl: string): void;
```

---

## 5. IndexedDB Triage Storage Contract

Module Path: `frontend/src/services/triageStorage.ts`

### 5.1 Interface Signatures

```typescript
export interface TriageStorageRecord {
  job_id: string; // KeyPath UUID
  decisions: Record<number, "COMMITTED" | "REJECTED">;
  duplicate_candidates: any[];
  last_updated: number; // Unix timestamp ms
  expires_at: number; // Unix timestamp ms = last_updated + 7 days
}

export interface ITriageStorageService {
  init(): Promise<void>;
  getJobDecisions(
    jobId: string,
  ): Promise<Record<number, "COMMITTED" | "REJECTED"> | null>;
  saveDecision(
    jobId: string,
    rowNumber: number,
    decision: "COMMITTED" | "REJECTED",
  ): Promise<void>;
  saveAllDecisions(
    jobId: string,
    decisions: Record<number, "COMMITTED" | "REJECTED">,
  ): Promise<void>;
  deleteJobRecord(jobId: string): Promise<void>;
  evictExpiredRecords(): Promise<number>; // Returns count of evicted records
}
```
