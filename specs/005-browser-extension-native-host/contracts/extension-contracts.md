# Extension Interface Contracts: Phase 5 — Manifest V3 Extension

**Feature**: `005-browser-extension-native-host`  
**Date**: 2026-10-20  
**Status**: Completed  
**Spec Reference**: [specs/005-browser-extension-native-host/spec.md](file:///d:/Coding/Vistarae/specs/005-browser-extension-native-host/spec.md)

---

## 1. External Connectable Contract (SPA $\rightarrow$ Extension)

Declared via `manifest.json`:

```json
"externally_connectable": {
  "matches": [
    "https://*.cloudfront.net/*",
    "http://localhost:5173/*"
  ]
}
```

The Vistarae Single-Page Application (SPA) sends messages directly to the background service worker using `chrome.runtime.sendMessage(EXTENSION_ID, message)`.

### 1.1 Action: `open_folder`

#### Request Payload

```typescript
interface OpenFolderRequest {
  action: "open_folder";
  /** Directory path, file:/// URI, or private UNC share path */
  path: string;
}
```

#### Success Response

```typescript
interface OpenFolderSuccessResponse {
  success: true;
  data: {
    action: "open_folder";
    path: string;
  };
}
```

#### Error Response (RFC 7807 ProblemDetails format)

```typescript
interface OpenFolderErrorResponse {
  success: false;
  error: {
    type: "native_host_not_found" | "native_host_error" | "security_violation";
    title: string;
    status: number;
    detail: string;
    code?: string;
  };
}
```

#### Example Usage in SPA

```typescript
export async function openLocalFolder(path: string): Promise<boolean> {
  const EXTENSION_ID = import.meta.env.VITE_VISTARAE_EXTENSION_ID;
  if (!window.chrome?.runtime?.sendMessage || !EXTENSION_ID) {
    showSetupToast("Chrome extension required to open local folders.");
    return false;
  }

  return new Promise((resolve) => {
    chrome.runtime.sendMessage(
      EXTENSION_ID,
      { action: "open_folder", path },
      (response) => {
        if (chrome.runtime.lastError || !response?.success) {
          showSetupToast(
            response?.error?.detail ||
              "Run python scripts/register_native_host.py to register folder opener.",
          );
          resolve(false);
        } else {
          resolve(true);
        }
      },
    );
  });
}
```

---

## 2. Internal Extension Message Contracts (Content Script $\leftrightarrow$ Service Worker)

Communication occurs over `chrome.runtime.sendMessage` and `chrome.tabs.sendMessage`.

### 2.1 Action Catalog

| Action               | Sender         | Receiver       | Payload                           | Response                                            | Description                                     |
| :------------------- | :------------- | :------------- | :-------------------------------- | :-------------------------------------------------- | :---------------------------------------------- |
| `TRIGGER_CAPTURE`    | Service Worker | Content Script | `{ text?: string, url?: string }` | `{ success: boolean }`                              | Awakens Shadow DOM overlay on active tab        |
| `EXTRACT_AND_CHECK`  | Content Script | Service Worker | `CapturePayload`                  | `ExtractAndCheckResponse`                           | Dispatches raw text to Gemini and PostGIS dedup |
| `SAVE_POI`           | Content Script | Service Worker | `CreatePoiPayload`                | `{ success: boolean, poi?: POI }`                   | Commits POI to database with idempotency key    |
| `GET_AUTH`           | Content Script | Service Worker | `{}`                              | `{ isAuthenticated: boolean, user: User \| null }`  | Inquires current login session state            |
| `LOGIN`              | Content Script | Service Worker | `{ email, password }`             | `{ success: boolean, user?: User, error?: string }` | In-page authentication against backend          |
| `REGISTER`           | Content Script | Service Worker | `{ email, password, full_name }`  | `{ success: boolean, user?: User, error?: string }` | In-page account creation                        |
| `GET_LISTS`          | Content Script | Service Worker | `{}`                              | `{ success: boolean, lists: List[] }`               | Retrieves user's travel lists for dropdown      |
| `CREATE_LIST`        | Content Script | Service Worker | `{ name, description }`           | `{ success: boolean, list: List }`                  | Creates list inline without modal close         |
| `NATIVE_OPEN_FOLDER` | POI Explorer   | Service Worker | `{ path: string }`                | `NativeHostResponse`                                | Triggers native messaging host from Explorer    |

---

## 3. Backend API Gateway Contracts

All requests initiated by the service worker attach:

```http
traceparent: 00-{trace_id}-{client_span_id}-01
X-Source: extension
X-Destination: backend
Authorization: Bearer <auth_token>
```

All mutating requests (`POST`, `PUT`, `DELETE`) also attach:

```http
Idempotency-Key: <uuidv4>
```

### 3.1 Extraction & Deduplication Endpoint: `POST /api/pois/extract-and-check`

#### Request Payload

```json
{
  "text": "Glacier Point is an overlook with a commanding view of Yosemite Valley, Half Dome, and Yosemite Falls, located on the south wall of Yosemite Valley at an elevation of 7,214 feet.",
  "source_url": "https://en.wikipedia.org/wiki/Glacier_Point",
  "page_title": "Glacier Point - Wikipedia"
}
```

#### Response (200 OK)

```json
{
  "candidate": {
    "name": "Glacier Point",
    "description": "Scenic overlook with panoramic views of Yosemite Valley, Half Dome, and waterfalls.",
    "category": "viewpoint",
    "address": "Glacier Point Rd, Yosemite National Park, CA 95389",
    "city": "Yosemite Valley",
    "state": "California",
    "country": "US",
    "latitude": 37.7303,
    "longitude": -119.5736,
    "rating": 5,
    "physical_effort": 1,
    "cost_tier": 1,
    "best_time": "Late Spring to Autumn",
    "tags": ["NPS", "overlook", "scenic"]
  },
  "deduplication": {
    "status": "NEARBY_PARENT",
    "distance_meters": 120.5,
    "similarity_score": 0.35,
    "existing_poi": {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Yosemite National Park",
      "address": "Yosemite National Park, CA",
      "city": "Yosemite Valley",
      "state": "California",
      "country": "US",
      "latitude": 37.7455,
      "longitude": -119.5936,
      "visit_state": "visited_return",
      "rating": 5,
      "tags": ["national-park", "macro-site"]
    }
  }
}
```

---

## 4. Silent Token Refresh Contract (AWS Cognito `InitiateAuth`)

Dispatched directly from the background service worker using `fetch`:

```http
POST / HTTP/1.1
Host: cognito-idp.<region>.amazonaws.com
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth

{
  "AuthFlow": "REFRESH_TOKEN_AUTH",
  "ClientId": "<COGNITO_APP_CLIENT_ID>",
  "AuthParameters": {
    "REFRESH_TOKEN": "<stored_refresh_token>"
  }
}
```

#### Success Response (200 OK)

```json
{
  "AuthenticationResult": {
    "AccessToken": "<new_jwt_access_token>",
    "ExpiresIn": 3600,
    "IdToken": "<new_jwt_id_token>",
    "TokenType": "Bearer"
  }
}
```
