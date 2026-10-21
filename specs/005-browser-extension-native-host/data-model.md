# Data Model & Storage Specifications: Phase 5 — Manifest V3 Extension & Native Host

**Feature**: `005-browser-extension-native-host`  
**Date**: 2026-10-20  
**Status**: Completed  
**Spec Reference**: [specs/005-browser-extension-native-host/spec.md](file:///d:/Coding/Vistarae/specs/005-browser-extension-native-host/spec.md)

---

## 1. Browser Extension Storage Entities

### 1.1 Local Storage (`chrome.storage.local`)

Persistent across browser restarts and service worker lifecycles. Encrypted and managed locally by Google Chrome.

```typescript
export interface StoredAuthSession {
  /** AWS Cognito Access Token (JWT format containing exp, sub, cognito:groups) */
  auth_token: string | null;

  /** AWS Cognito ID Token (JWT format containing email, name, profile claims) */
  id_token: string | null;

  /** AWS Cognito Refresh Token for silent background renewal */
  refresh_token: string | null;

  /** Cached user profile summary */
  user: UserProfileSummary | null;
}

export interface UserProfileSummary {
  id: string; // UUIDv4
  email: string; // User email
  full_name: string; // Full name
  tier: "LOW" | "HIGH"; // User quota tier
}
```

### 1.2 Sync Storage (`chrome.storage.sync`)

Synchronized across Google Chrome profiles when Chrome Sync is enabled; falls back to local storage if disabled.

```typescript
export interface StoredExtensionSettings {
  /** Backend API gateway URL (default: "http://localhost:8000") */
  backendUrl: string;

  /** Preferred theme mode for POI Explorer and Overlay */
  theme: "light" | "dark" | "system";

  /** Default geoproximity search radius in miles (default: 25) */
  defaultSearchRadiusMiles: number;
}
```

---

## 2. In-Memory Service Worker State

Manifest V3 service workers are ephemeral. The in-memory state is maintained while the worker is active and initialized cleanly on worker wakeup.

```typescript
export interface ServiceWorkerState {
  /** Active in-flight token refresh promise (single-flight mutex) */
  refreshPromise: Promise<string> | null;

  /** Active Native Messaging Host port (ephemeral connection) */
  nativePort: chrome.runtime.Port | null;
}
```

### Token Lifecycle & Refresh State Transitions

```
                    +---------------------------+
                    | No Token / Storage Empty  |
                    +---------------------------+
                                  |
                           Login / Register
                                  v
                    +---------------------------+
                    |  Active Authenticated     |
                    | (exp - now > 300 seconds) |
                    +---------------------------+
                                  |
                   Pre-flight check: exp <= 300s
                                  v
                    +---------------------------+
         +--------> |  Refresh In-Flight Mutex  | <--------+
         |          | (refreshPromise active)   |          |
         |          +---------------------------+          |
  Parallel Req 2                  |                 Parallel Req 3
(awaits promise)                  |                 (awaits promise)
                                  v
                        Cognito InitiateAuth
                       (REFRESH_TOKEN_AUTH)
                                  |
                   +--------------+--------------+
                   |                             |
             200 OK Response               400/401 Failure
                   |                             |
                   v                             v
     +---------------------------+ +---------------------------+
     |   Tokens Updated in       | | Tokens Purged from        |
     |   chrome.storage.local    | | Storage; Prompt Login     |
     +---------------------------+ +---------------------------+
```

---

## 3. Scraper & Content Script Entities

### 3.1 Extracted POI Candidate Data (`ExtractedPoiData`)

Produced by `BasePoiParser` implementations (`GoogleMapsParser`, `RoadtrippersParser`, `TripAdvisorParser`, `GenericSelectionParser`) and consumed by the Shadow DOM form and backend extraction service.

```typescript
export interface ExtractedPoiData {
  /** Destination name */
  name: string;

  /** Extracted or inferred description */
  description: string | null;

  /** Category classification */
  category:
    | "viewpoint"
    | "trail"
    | "historic"
    | "museum"
    | "food"
    | "park"
    | "other";

  /** Street address */
  address: string | null;

  /** City / locality */
  city: string | null;

  /** State / province / prefecture */
  state: string | null;

  /** ISO 3166-1 alpha-2 country code */
  country: string | null;

  /** Canonical WGS-84 latitude (-90.0 to 90.0) */
  latitude: number | null;

  /** Canonical WGS-84 longitude (-180.0 to 180.0) */
  longitude: number | null;

  /** Personal traveler rating (1 to 5 stars) */
  rating: number;

  /** Physical effort rating (1 to 5) */
  physical_effort: number;

  /** Cost tier (1 to 4) */
  cost_tier: number;

  /** Best season / time to visit (e.g. "Spring", "Autumn") */
  best_time: string | null;

  /** Array of tag labels */
  tags: string[];

  /** Canonical source webpage URL */
  source_url: string;

  /** Document title of the source page */
  page_title: string;

  /** Thumbnail image preview URL */
  image_url: string | null;
}
```

### 3.2 Deduplication & Collision Candidate

Returned by `/api/pois/extract-and-check` to inform the user of potential duplicate places or nearby macro-sites.

```typescript
export interface DeduplicationResult {
  /** Classification outcome */
  status: "UNIQUE_LOCATION" | "POTENTIAL_DUPLICATE" | "NEARBY_PARENT";

  /** Geodesic distance in meters (if candidate found within radius) */
  distance_meters: number | null;

  /** Trigram string similarity score between 0.0 and 1.0 */
  similarity_score: number | null;

  /** Existing database POI summary (for side-by-side comparison) */
  existing_poi: ExistingPoiSummary | null;
}

export interface ExistingPoiSummary {
  id: string; // UUIDv4
  name: string;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string;
  latitude: number;
  longitude: number;
  visit_state: "not_visited" | "visited_return" | "visited_do_not_return";
  rating: number;
  tags: string[];
}
```

---

## 4. Native Messaging Host Entities (`folder_dispatcher.py`)

### 4.1 Inbound Request Schema

Transmitted from Google Chrome over unbuffered standard input framed with a 4-byte native-endian integer length.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "NativeHostRequest",
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": ["open_folder", "ping"]
    },
    "path": {
      "type": "string",
      "description": "Local filesystem directory path, file:/// URI, or private UNC network share"
    }
  },
  "required": ["action"],
  "additionalProperties": false
}
```

### 4.2 Outbound Response Schema

Transmitted from `folder_dispatcher.py` to Google Chrome over unbuffered standard output framed with a 4-byte native-endian integer length.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "NativeHostResponse",
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["ok", "error"]
    },
    "action": {
      "type": "string"
    },
    "path": {
      "type": "string",
      "description": "Normalized canonical path that was opened"
    },
    "version": {
      "type": "string",
      "description": "Host version (returned on ping)"
    },
    "platform": {
      "type": "string",
      "description": "Operating system platform (e.g. win32, darwin, linux)"
    },
    "code": {
      "type": "string",
      "enum": [
        "ILLEGAL_CHARACTERS",
        "NULL_BYTE_DETECTED",
        "UNTRUSTED_NETWORK_HOST",
        "PATH_NOT_FOUND",
        "NETWORK_TIMEOUT",
        "MALFORMED_JSON",
        "EXECUTION_FAILED"
      ]
    },
    "message": {
      "type": "string",
      "description": "Human-readable diagnostic error message"
    }
  },
  "required": ["status"],
  "additionalProperties": false
}
```

---

## 5. Chrome Native Messaging Host Manifest

File: `native_host/com.vistarae.folder_opener.json`

```json
{
  "name": "com.vistarae.folder_opener",
  "description": "Vistarae Local Folder Opener Native Host",
  "path": "D:\\Coding\\Vistarae\\native_host\\run_dispatcher.bat",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://<EXTENSION_ID>/"]
}
```

_(On macOS and Linux, the `"path"` points directly to `/path/to/folder_dispatcher.py` marked executable via `chmod +x`)._
