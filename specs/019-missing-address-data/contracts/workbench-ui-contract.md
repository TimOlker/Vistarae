# Frontend Workbench UI Contract: Exemption Checkboxes & Filtering

**Feature**: `019-missing-address-data`  
**Date**: 2026-11-18  
**Component**: `frontend/src/components/ingest/CSVImportWorkbenchModal.tsx`  

---

## 1. Type Definitions & Filter State

```typescript
export type CompletenessFilter =
  | "all"
  | "complete"
  | "incomplete"
  | "needs_action"
  | "exempted"
  | "missing_photo"
  | "missing_location"
  | "missing_websites";
```

### Missing Fields Calculation (`getCandidateMissingFields`)

```typescript
function getCandidateMissingFields(cand: {
  hero_image_url?: string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  street_address?: string | null;
  official_url?: string | null;
  related_websites?: any[] | null;
  no_websites?: boolean | null;
  no_address?: boolean | null;
}): string[] {
  const missing: string[] = [];
  
  // Photo Rule
  const hasPhoto = Boolean(cand.hero_image_url && cand.hero_image_url.trim());
  if (!hasPhoto) missing.push("Photo");

  // Coordinates Rule (Mandatory for map rendering)
  const hasCoords = cand.latitude != null && cand.longitude != null;
  if (!hasCoords) missing.push("Coordinates");

  // Street Address Rule (Exempted if no_address is true)
  const hasStreet = Boolean(cand.street_address && cand.street_address.trim()) || Boolean(cand.no_address);
  if (!hasStreet) missing.push("Street Address");

  // Websites Rule (Exempted if no_websites is true)
  const hasWebsites =
    Boolean(cand.official_url && cand.official_url.trim()) ||
    Boolean(cand.related_websites && cand.related_websites.length > 0) ||
    Boolean(cand.no_websites);
  if (!hasWebsites) missing.push("Websites");

  return missing;
}

function isCandidateComplete(cand: CandidateItem): boolean {
  return getCandidateMissingFields(cand).length === 0;
}
```

---

## 2. Table Filtering Contract

```typescript
// Filter evaluation inside filteredCandidates memo:
if (completenessFilter === "complete") {
  if (!isCandidateComplete(cand)) return false;
} else if (completenessFilter === "incomplete") {
  if (isCandidateComplete(cand)) return false;
} else if (completenessFilter === "needs_action") {
  // Candidate has at least one missing field that is NOT exempted
  const missing = getCandidateMissingFields(cand);
  if (missing.length === 0) return false;
} else if (completenessFilter === "exempted") {
  // Candidate has at least one active exemption flag
  const hasExemption = Boolean(cand.no_address) || Boolean(cand.no_websites);
  if (!hasExemption) return false;
} else if (completenessFilter === "missing_photo") {
  if (Boolean(cand.hero_image_url && cand.hero_image_url.trim())) return false;
} else if (completenessFilter === "missing_location") {
  if (cand.latitude != null && cand.longitude != null && (Boolean(cand.street_address && cand.street_address.trim()) || Boolean(cand.no_address))) return false;
} else if (completenessFilter === "missing_websites") {
  if (Boolean(cand.official_url && cand.official_url.trim()) || Boolean(cand.related_websites && cand.related_websites.length > 0) || Boolean(cand.no_websites)) return false;
}
```

---

## 3. Multi-Row Toolbar Batch Action Contract

When `selectedCandidateIds.size >= 2`, render batch exemption controls:

```tsx
<div className="flex items-center gap-2">
  <button
    type="button"
    onClick={() => handleBatchExemption("no_address", true)}
    className="btn-secondary text-xs px-2 py-1"
    data-testid="batch-mark-no-address-button"
  >
    Mark Selected: No Address
  </button>
  <button
    type="button"
    onClick={() => handleBatchExemption("no_websites", true)}
    className="btn-secondary text-xs px-2 py-1"
    data-testid="batch-mark-no-websites-button"
  >
    Mark Selected: No Websites
  </button>
  <button
    type="button"
    onClick={() => handleBatchExemption("clear_all", false)}
    className="btn-secondary text-xs px-2 py-1 text-gray-500 hover:text-gray-700"
    data-testid="batch-clear-exemptions-button"
  >
    Clear Selected Exemptions
  </button>
</div>
```

---

## 4. Candidate Detail Editor Contract

Within the right-hand candidate detail editor panel:

- **Data Availability / Exemptions Card**:
  - `[ ] No address available / Acceptable` (`no_address`)
  - `[ ] No website available / Acceptable` (`no_websites`)
- **Auto-Reset Interactions**:
  - `onStreetAddressChange(val)`: If `val.trim().length > 0` and `no_address === true`, automatically set `setNoAddress(false)`.
  - `onWebsiteUrlChange(val)`: If `val.trim().length > 0` and `no_websites === true`, automatically set `setNoWebsites(false)`.
