/**
 * Vistarae Content Script
 * Captures webpage selection, enforces user authentication, and injects Shadow DOM editor.
 */

let hostElement = null;
let shadowRoot = null;

/**
 * Ensures clean Shadow DOM host element.
 */
function getOrCreateShadowRoot() {
  if (hostElement && shadowRoot) {
    return shadowRoot;
  }

  hostElement = document.createElement("vistarae-capture-root");
  hostElement.id = "vistarae-capture-host";
  document.body.appendChild(hostElement);

  shadowRoot = hostElement.attachShadow({ mode: "open" });

  // Inject scoped stylesheet
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = chrome.runtime.getURL("content/overlay.css");
  shadowRoot.appendChild(link);

  return shadowRoot;
}

function removeModal() {
  if (shadowRoot) {
    const backdrop = shadowRoot.querySelector(".vistarae-backdrop");
    if (backdrop) backdrop.remove();
  }
  // Only remove entire host if no toast is actively visible
  if (hostElement && shadowRoot && !shadowRoot.querySelector(".vistarae-toast")) {
    hostElement.remove();
    hostElement = null;
    shadowRoot = null;
  }
}

/**
 * Displays a toast notification.
 */
function showToast(message, isError = false) {
  const root = getOrCreateShadowRoot();
  const toast = document.createElement("div");
  toast.className = "vistarae-toast";
  toast.style.borderLeft = isError ? "4px solid #ef4444" : "4px solid #10b981";
  toast.innerHTML = `
    <span>${isError ? "⚠️" : "✨"}</span>
    <span>${escapeHtml(message)}</span>
  `;
  root.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => {
      toast.remove();
      if (!root.querySelector(".vistarae-modal") && !root.querySelector(".vistarae-toast")) {
        if (hostElement) {
          hostElement.remove();
          hostElement = null;
          shadowRoot = null;
        }
      }
    }, 300);
  }, 3500);
}


function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

const BLACKLISTED_OFFICIAL_WEBSITE_DOMAINS = [
  "google.",
  "bing.com",
  "yahoo.com",
  "duckduckgo.com",
  "baidu.com",
  "yandex.com",
  "tripadvisor.",
  "roadsideamerica.com",
  "locationscout.net",
  "shothotspot.com",
  "atlasobscura.com",
  "wikipedia.org",
  "wikimedia.org",
  "yelp.com",
  "facebook.com",
  "instagram.com",
  "reddit.com",
  "twitter.com",
  "x.com",
  "tiktok.com",
  "pinterest.com",
  "threads.net",
  "youtube.com",
];

function sanitizeOfficialWebsite(url) {
  if (!url || typeof url !== "string") return null;
  let cleanUrl = url.trim();
  if (!cleanUrl) return null;

  try {
    let parsed = new URL(cleanUrl);
    // Unwrap Google redirect URLs (/url?q=... or /url?url=...)
    if (parsed.hostname.includes("google.") && parsed.pathname.startsWith("/url")) {
      const qParam = parsed.searchParams.get("q") || parsed.searchParams.get("url");
      if (qParam && (qParam.startsWith("http://") || qParam.startsWith("https://"))) {
        cleanUrl = qParam.trim();
        parsed = new URL(cleanUrl);
      }
    }

    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }

    const host = parsed.hostname.toLowerCase();
    for (const domain of BLACKLISTED_OFFICIAL_WEBSITE_DOMAINS) {
      if (host.includes(domain)) {
        return null;
      }
    }

    return parsed.href;
  } catch (e) {
    return null;
  }
}

/**
 * Detects whether an image URL points to a static map, map tile, streetview tile, or placeholder.
 */
function isMapOrPlaceholderImageUrl(url) {
  if (!url || typeof url !== "string") return true;
  const u = url.trim().toLowerCase();
  if (!u || (!u.startsWith("http://") && !u.startsWith("https://"))) return true;

  const mapOrPlaceholderPatterns = [
    "staticmap",
    "/static_map",
    "maps.google.com/maps/api",
    "maps.googleapis.com/maps/api",
    "streetviewpixels",
    "maps.gstatic.com",
    "google.com/maps/vt",
    "tile.openstreetmap.org",
    "tile.openstreetmap",
    "tile.mapbox",
    "data:image/gif",
    "data:image/svg",
    "default_avatar",
    "branding/googlelogo",
    "cleardot.gif",
    "grey_header_tile",
    "transparent.png",
    "/tactile/omnibox/",
  ];

  return mapOrPlaceholderPatterns.some((pattern) => u.includes(pattern));
}

/**
 * Searches Google Maps place panel specifically for subject/exhibit photos.
 */
function findGoogleMapsPlacePhoto() {
  const candidates = Array.from(
    document.querySelectorAll(
      'button[jsaction*="heroHeaderImage"] img, ' +
      'button[aria-label*="Photo of"] img, ' +
      'button[aria-label*="Photos"] img, ' +
      'button.aoRNLd img, ' +
      'div.m6QErb button img, ' +
      'div[class*="gallery"] img, ' +
      'button[data-photo-index] img, ' +
      'img[src*="googleusercontent.com/p/"], ' +
      'img[src*="ggpht.com/p/"]'
    )
  );

  for (const img of candidates) {
    const src = img.currentSrc || img.src || img.getAttribute("src");
    if (!src || isMapOrPlaceholderImageUrl(src)) continue;
    if (src.includes("googleusercontent.com/p/") || src.includes("ggpht.com/p/")) {
      return src;
    }
    if (img.closest('button[jsaction*="heroHeaderImage"], button[aria-label*="Photo of"]')) {
      return src;
    }
  }

  // Broader check for any place content image uploaded to Google user content
  const allPlaceImgs = Array.from(document.querySelectorAll('div[role="main"] img, div[aria-label] img'));
  for (const img of allPlaceImgs) {
    const src = img.currentSrc || img.src || img.getAttribute("src");
    if (src && !isMapOrPlaceholderImageUrl(src) && (src.includes("googleusercontent.com/p/") || src.includes("ggpht.com/p/"))) {
      return src;
    }
  }

  return null;
}

/**
 * Dispatches a message to the background service worker with x-source and x-destination set.
 */
function sendExtensionMessage(message, callback) {
  const enriched = {
    "x-source": "extension",
    "x-destination": "backend",
    ...message,
  };
  return chrome.runtime.sendMessage(enriched, callback);
}

/**
 * Renders the loading modal state.
 */
function showLoadingModal() {
  const root = getOrCreateShadowRoot();

  // Clear previous modal
  const existing = root.querySelector(".vistarae-backdrop");
  if (existing) existing.remove();

  const backdrop = document.createElement("div");
  backdrop.className = "vistarae-backdrop";
  backdrop.innerHTML = `
    <div class="vistarae-modal" style="max-width: 420px;">
      <div class="vistarae-header">
        <div class="vistarae-title-wrap">
          <div class="vistarae-logo-icon">V</div>
          <h2 class="vistarae-title">Vistarae Ingestion</h2>
        </div>
        <button class="vistarae-close-btn" id="vistarae-cancel-load">&times;</button>
      </div>
      <div class="vistarae-loading-center">
        <div class="vistarae-spinner"></div>
        <p style="font-size: 14px; color: #475569; margin: 0;">Extracting POI entities & geocoding...</p>
      </div>
    </div>
  `;

  root.appendChild(backdrop);
  backdrop.querySelector("#vistarae-cancel-load").addEventListener("click", removeModal);
}

/**
 * Renders the Authentication Modal (Login & Register).
 */
function renderAuthModal(pendingPayload = null) {
  const root = getOrCreateShadowRoot();
  const existing = root.querySelector(".vistarae-backdrop");
  if (existing) existing.remove();

  let activeMode = "login"; // "login" | "register"

  const backdrop = document.createElement("div");
  backdrop.className = "vistarae-backdrop";
  backdrop.innerHTML = `
    <div class="vistarae-modal" style="max-width: 440px;">
      <div class="vistarae-header">
        <div class="vistarae-title-wrap">
          <div class="vistarae-logo-icon">V</div>
          <h2 class="vistarae-title">Vistarae Account</h2>
        </div>
        <button class="vistarae-close-btn" id="vistarae-auth-close">&times;</button>
      </div>

      <div class="vistarae-auth-tabs">
        <button class="vistarae-auth-tab active" id="tab-login">Sign In</button>
        <button class="vistarae-auth-tab" id="tab-register">Create Account</button>
      </div>

      <div class="vistarae-body" style="padding-top: 16px;">
        <div class="vistarae-auth-error" id="v-auth-error"></div>

        <div class="vistarae-field-group" id="group-fullname" style="display: none;">
          <label class="vistarae-label">Full Name</label>
          <input type="text" class="vistarae-input" id="v-fullname" placeholder="Alex Traveler" />
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Email Address</label>
          <input type="email" class="vistarae-input" id="v-email" placeholder="traveler@example.com" />
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Password</label>
          <input type="password" class="vistarae-input" id="v-password" placeholder="••••••••" />
        </div>
      </div>

      <div class="vistarae-footer">
        <button class="vistarae-btn vistarae-btn-secondary" id="vistarae-auth-cancel">Cancel</button>
        <button class="vistarae-btn vistarae-btn-primary" id="vistarae-auth-submit">Sign In</button>
      </div>
    </div>
  `;

  root.appendChild(backdrop);

  const errorBox = backdrop.querySelector("#v-auth-error");
  const tabLogin = backdrop.querySelector("#tab-login");
  const tabRegister = backdrop.querySelector("#tab-register");
  const groupFullname = backdrop.querySelector("#group-fullname");
  const submitBtn = backdrop.querySelector("#vistarae-auth-submit");

  backdrop.querySelector("#vistarae-auth-close").addEventListener("click", removeModal);
  backdrop.querySelector("#vistarae-auth-cancel").addEventListener("click", removeModal);

  tabLogin.addEventListener("click", () => {
    activeMode = "login";
    tabLogin.classList.add("active");
    tabRegister.classList.remove("active");
    groupFullname.style.display = "none";
    submitBtn.textContent = "Sign In";
    errorBox.style.display = "none";
  });

  tabRegister.addEventListener("click", () => {
    activeMode = "register";
    tabRegister.classList.add("active");
    tabLogin.classList.remove("active");
    groupFullname.style.display = "flex";
    submitBtn.textContent = "Create Account";
    errorBox.style.display = "none";
  });

  submitBtn.addEventListener("click", () => {
    const email = backdrop.querySelector("#v-email").value.trim();
    const password = backdrop.querySelector("#v-password").value;
    const fullName = backdrop.querySelector("#v-fullname").value.trim();

    if (!email || !password) {
      errorBox.textContent = "Please provide both email and password.";
      errorBox.style.display = "block";
      return;
    }

    if (activeMode === "register" && password.length < 6) {
      errorBox.textContent = "Password must be at least 6 characters long.";
      errorBox.style.display = "block";
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Please wait...";
    errorBox.style.display = "none";

    const action = activeMode === "register" ? "REGISTER" : "LOGIN";
    const payload = activeMode === "register"
      ? { email, password, full_name: fullName || null }
      : { email, password };

    sendExtensionMessage({ action, payload }, (res) => {
      submitBtn.disabled = false;
      submitBtn.textContent = activeMode === "register" ? "Create Account" : "Sign In";

      if (res && res.success) {
        showToast(`Welcome back, ${res.data?.user?.full_name || email}!`);
        if (pendingPayload) {
          executeExtractionAndCheck(pendingPayload, res.data?.user);
        } else {
          removeModal();
        }
      } else {
        errorBox.textContent = res?.error || "Authentication failed. Please check your credentials.";
        errorBox.style.display = "block";
      }
    });
  });
}

/**
 * Maps Google Maps category text to Vistarae POI type enum.
 */
function mapGoogleCategoryToPoiType(cat) {
  if (!cat) return "site to see";
  const c = cat.toLowerCase();
  if (c.includes("viewpoint") || c.includes("lookout") || c.includes("photo") || c.includes("vista") || c.includes("scenic") || c.includes("overlook")) {
    return "photo location";
  }
  if (c.includes("hike") || c.includes("trail") || c.includes("tour") || c.includes("adventure") || c.includes("experience") || c.includes("rafting") || c.includes("climb")) {
    return "experience";
  }
  if (c.includes("restaurant") || c.includes("cafe") || c.includes("coffee") || c.includes("bar") || c.includes("bakery") || c.includes("food") || c.includes("winery") || c.includes("brewery")) {
    return "food/drink";
  }
  if (c.includes("hotel") || c.includes("motel") || c.includes("resort") || c.includes("campground") || c.includes("lodging") || c.includes("hostel") || c.includes("cabin")) {
    return "lodging";
  }
  if (c.includes("station") || c.includes("airport") || c.includes("transit") || c.includes("ferry") || c.includes("bus")) {
    return "transit";
  }
  return "site to see";
}

/**
 * Parses Google Maps URL and DOM to detect if a place is selected.
 */
function parseGoogleMapsPlace() {
  const url = window.location.href;
  const isGoogleMaps =
    (window.location.hostname.includes("google.") && window.location.pathname.includes("/maps")) ||
    window.location.hostname === "maps.google.com";

  if (!isGoogleMaps) {
    return null;
  }

  let placeName = null;
  let lat = null;
  let lng = null;

  // 1. Extract place name from URL path /maps/place/<name>
  const placeMatch = window.location.pathname.match(/\/maps\/place\/([^/@?]+)/);
  if (placeMatch) {
    const raw = placeMatch[1];
    if (!raw.startsWith("data=")) {
      placeName = decodeURIComponent(raw.replace(/\+/g, " ")).trim();
      if (placeName.includes(",")) {
        placeName = placeName.split(",")[0].trim();
      }
    }
  }

  // Fallback place name from /maps/search/<name>
  if (!placeName) {
    const searchMatch = window.location.pathname.match(/\/maps\/search\/([^/@?]+)/);
    if (searchMatch) {
      placeName = decodeURIComponent(searchMatch[1].replace(/\+/g, " ")).trim();
      if (placeName.includes(",")) {
        placeName = placeName.split(",")[0].trim();
      }
    }
  }

  // 2. DOM enrichment: Check heading element (h1) or document.title
  const h1 =
    document.querySelector('h1.DUwDvf') ||
    document.querySelector('h1[class*="fontHeadlineLarge"]') ||
    document.querySelector('h1');
  if (h1 && h1.textContent.trim()) {
    placeName = h1.textContent.trim();
  } else if (!placeName && document.title) {
    const cleanTitle = document.title.replace(/\s*[-–—]\s*Google Maps.*$/i, "").trim();
    if (cleanTitle && !cleanTitle.toLowerCase().includes("google maps")) {
      placeName = cleanTitle;
    }
  }

  // 3. Extract viewport center coordinates /@<lat>,<lng>
  let centerLat = null;
  let centerLng = null;
  const centerMatch = url.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (centerMatch) {
    centerLat = parseFloat(centerMatch[1]);
    centerLng = parseFloat(centerMatch[2]);
  }

  // Extract exact pin coordinates (!3d<lat>!4d<lng>)
  // Google Maps URLs frequently include prior search/navigation history in data=
  // (e.g. 1m7!3m6!2sYellowstone!3d...!4d... followed by 3m5!1s...Alcatraz!3d...!4d...)
  // We match all pins and select the one closest to the active viewport center, or the last pin.
  const pinMatches = Array.from(url.matchAll(/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/g));
  if (pinMatches.length > 0) {
    if (centerLat !== null && centerLng !== null && pinMatches.length > 1) {
      let bestMatch = pinMatches[pinMatches.length - 1];
      let minDiff = Infinity;
      for (const m of pinMatches) {
        const mLat = parseFloat(m[1]);
        const mLng = parseFloat(m[2]);
        const diff = Math.hypot(mLat - centerLat, mLng - centerLng);
        if (diff < minDiff) {
          minDiff = diff;
          bestMatch = m;
        }
      }
      lat = parseFloat(bestMatch[1]);
      lng = parseFloat(bestMatch[2]);
    } else {
      const last = pinMatches[pinMatches.length - 1];
      lat = parseFloat(last[1]);
      lng = parseFloat(last[2]);
    }
  } else if (centerLat !== null && centerLng !== null) {
    lat = centerLat;
    lng = centerLng;
  }

  // If still no coordinates, check search params ?q=lat,lng or ?ll=lat,lng
  if (lat === null || lng === null) {
    const qMatch = window.location.search.match(/[?&](?:q|ll)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
    if (qMatch) {
      lat = parseFloat(qMatch[1]);
      lng = parseFloat(qMatch[2]);
    }
  }

  // If neither place name nor coordinates found, no place is selected on the map
  if (!placeName && lat === null) {
    return { isGoogleMaps: true, hasPlace: false };
  }

  // 4. Extract additional DOM metadata if available
  const catBtn =
    document.querySelector('button[jsaction*="pane.rating.category"]') ||
    document.querySelector('button.DkEaL') ||
    document.querySelector('div.fontBodyMedium button');
  const category = catBtn ? catBtn.textContent.trim() : null;

  const addrElem =
    document.querySelector('button[data-item-id="address"]') ||
    document.querySelector('button[aria-label*="Address:"]');
  const address = addrElem
    ? (addrElem.getAttribute("aria-label")?.replace(/^Address:\s*/i, "") || addrElem.textContent.trim())
    : null;

  let rating = 4;
  const ratingElem =
    document.querySelector('div.F7nice span[aria-hidden="true"]') ||
    document.querySelector('span[aria-label*="stars"]');
  if (ratingElem) {
    const numMatch = ratingElem.textContent.match(/(\d+(?:\.\d+)?)/);
    if (numMatch) {
      rating = Math.round(parseFloat(numMatch[1]));
    }
  }

  const webElem =
    document.querySelector('a[data-item-id="authority"]') ||
    document.querySelector('a[aria-label*="Website:"]');
  const website = webElem ? sanitizeOfficialWebsite(webElem.href || webElem.textContent.trim()) : null;

  const phoneElem =
    document.querySelector('button[data-item-id*="phone"]') ||
    document.querySelector('button[aria-label*="Phone:"]');
  const phoneNumber = phoneElem
    ? (phoneElem.getAttribute("aria-label")?.replace(/^Phone:\s*/i, "") || phoneElem.textContent.trim())
    : null;

  const descElem =
    document.querySelector('div.PYvSYb') ||
    document.querySelector('div[class*="editorial"]') ||
    document.querySelector('div.fontBodySmall');
  const description = descElem ? descElem.textContent.trim() : null;

  const imageUrl = findGoogleMapsPlacePhoto();

  return {
    isGoogleMaps: true,
    hasPlace: true,
    placeName: placeName || "Google Maps Place",
    lat,
    lng,
    category,
    poiType: mapGoogleCategoryToPoiType(category),
    address,
    rating,
    website,
    phoneNumber,
    description,
    imageUrl,
  };
}

/**
 * Parses Google Search Knowledge Graph / Entity Panels (#sv=, knowledge cards).
 */
function parseGoogleSearchPlace() {
  const isGoogleSearch =
    window.location.hostname.includes("google.") &&
    (window.location.pathname === "/search" || window.location.pathname.startsWith("/search"));

  if (!isGoogleSearch) {
    return null;
  }

  let placeName = null;
  let category = null;
  let address = null;
  let website = null;
  let phoneNumber = null;
  let description = null;
  let imageUrl = null;
  let city = null;
  let state = null;
  let country = null;
  let postalCode = null;

  // 1. Decode place name from #sv= hash if present (Google entity side-view panel)
  if (window.location.hash.startsWith("#sv=")) {
    try {
      const b64 = window.location.hash.slice(4).replace(/-/g, "+").replace(/_/g, "/");
      const decoded = atob(b64);
      const matches = decoded.match(/[\x20-\x7E]{4,}/g);
      if (matches) {
        const candidates = matches.filter(
          (s) => !s.startsWith("/m/") && !s.startsWith("http") && s.trim().length > 3
        );
        if (candidates.length > 0) {
          candidates.sort((a, b) => b.length - a.length);
          placeName = candidates[0].trim();
        }
      }
    } catch (e) {
      // ignore hash decode error
    }
  }

  // 2. Knowledge Graph DOM Selectors
  const titleEl = document.querySelector(
    '[data-attrid="title"], h2.qrShPb, .kno-ecr-pt, div[role="heading"][aria-level="2"], div[role="dialog"] h2, div[data-entity-id] h2'
  );
  if (titleEl && titleEl.textContent.trim()) {
    const domTitle = titleEl.textContent.trim();
    if (!domTitle.toLowerCase().startsWith("top sights") && !domTitle.toLowerCase().includes("search results")) {
      placeName = domTitle;
    }
  }

  // 3. Subtitle / Category (e.g. "City in Pennsylvania" or "Museum in Philadelphia, Pennsylvania")
  const US_STATES_SET = new Set([
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire",
    "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington", "west virginia",
    "wisconsin", "wyoming", "district of columbia"
  ]);

  const subtitleEl = document.querySelector('[data-attrid="subtitle"], .FLP8od, .kno-header div');
  if (subtitleEl) {
    category = subtitleEl.textContent.trim();
    const locMatch = category.match(/in\s+([^,]+)(?:,\s*([^,]+))?$/i);
    if (locMatch) {
      const firstPart = locMatch[1].trim();
      const secondPart = locMatch[2] ? locMatch[2].trim() : null;
      if (secondPart) {
        city = firstPart;
        state = secondPart;
      } else {
        // Single location part after "in", e.g. "City in Pennsylvania"
        const isCityOrTown = /city|town|municipality|village|borough|capital/i.test(category);
        const isKnownState = US_STATES_SET.has(firstPart.toLowerCase());
        if (isKnownState || isCityOrTown) {
          state = firstPart;
          if (isCityOrTown && placeName) {
            city = placeName;
          }
        } else {
          city = firstPart;
        }
      }
    }
  }

  // 4. Address (e.g. "2027 Fairmount Ave, Philadelphia, PA 19130")
  const addrEl = document.querySelector('[data-attrid*="address"], .LrzXr');
  if (addrEl) {
    address = addrEl.textContent.trim().replace(/^Address:\s*/i, "");
    const addrParts = address.split(",");
    if (addrParts.length >= 2) {
      const cityCandidate = addrParts[addrParts.length - 2].trim();
      if (cityCandidate) city = cityCandidate;

      const stateZip = addrParts[addrParts.length - 1].trim();
      const stateZipMatch = stateZip.match(/([A-Za-z\s]+)(?:\s+(\d{5}(?:-\d{4})?))?/);
      if (stateZipMatch) {
        state = stateZipMatch[1].trim();
        if (stateZipMatch[2]) postalCode = stateZipMatch[2].trim();
      }
    }
  }

  // Safety check: City should never be equal to State unless it's a known city-state
  if (city && state && city.toLowerCase() === state.toLowerCase()) {
    if (placeName && placeName.toLowerCase() !== state.toLowerCase()) {
      city = placeName;
    } else {
      city = null;
    }
  }


  // 5. Official Website
  let webEl = document.querySelector('a[data-attrid*="visit_official_site"], a[data-attrid*="website"], div[data-attrid*="website"] a');
  if (!webEl) {
    // Only search specifically for explicit "Website" or "Official site" buttons inside knowledge cards
    const candidates = Array.from(document.querySelectorAll('.kp-wholepage a, #rhs a, [data-attrid] a, div.xpdopen a, div[role="complementary"] a'));
    for (const a of candidates) {
      const aria = (a.getAttribute("aria-label") || "").toLowerCase();
      const txt = (a.textContent || "").toLowerCase().trim();
      if ((aria.includes("website") || txt === "website" || txt === "official site") && a.href) {
        webEl = a;
        break;
      }
    }
  }
  if (webEl && webEl.href) {
    website = sanitizeOfficialWebsite(webEl.href);
  }

  // 6. Phone
  const phoneEl = document.querySelector('[data-attrid*="phone"]');
  if (phoneEl) {
    phoneNumber = phoneEl.textContent.trim().replace(/^Phone:\s*/i, "");
  }

  // 7. Description
  const descEl = document.querySelector('[data-attrid*="description"], div.kno-rdesc span');
  if (descEl) {
    description = descEl.textContent.trim().replace(/^Description\s*/i, "");
  }

  // 8. Image
  const imgEl = document.querySelector('img[data-attrid*="image"], div.kno-fb-ctx img');
  if (imgEl && imgEl.src && !imgEl.src.includes("data:image/gif")) {
    imageUrl = imgEl.src;
  }

  // 9. Fallback: if no specific knowledge entity, fallback to query string parameter
  if (!placeName) {
    const urlParams = new URLSearchParams(window.location.search);
    const q = urlParams.get("q");
    if (q) {
      placeName = q.trim();
    }
  }

  if (!placeName) {
    return null;
  }

  const tags = [];
  if (category) tags.push(category.toLowerCase());
  if (city) tags.push(city.toLowerCase());

  return {
    isGoogleSearch: true,
    hasPlace: true,
    placeName,
    lat: null,
    lng: null,
    category,
    poiType: category ? mapGoogleCategoryToPoiType(category) : "site to see",
    address,
    city,
    state,
    country: "US",
    postalCode,
    tags,
    website,
    phoneNumber,
    description: description || (address ? `${placeName} located at ${address}.` : `Point of interest captured from Google: ${placeName}.`),
    imageUrl,
  };
}

/**
 * Parses Atlas Obscura URL and DOM to detect and extract place details.
 */
function parseAtlasObscuraPlace() {

  const url = window.location.href;
  const isAtlasObscura =
    window.location.hostname.includes("atlasobscura.com") &&
    window.location.pathname.includes("/places/");

  if (!isAtlasObscura) {
    return null;
  }

  // 1. Search application/ld+json scripts for Place / TouristAttraction
  let placeJson = null;
  const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of jsonLdScripts) {
    try {
      const data = JSON.parse(script.textContent || "{}");
      const types = Array.isArray(data["@type"]) ? data["@type"] : [data["@type"]];
      if (
        types.some((t) =>
          [
            "Place",
            "TouristAttraction",
            "Restaurant",
            "LandmarksOrHistoricalBuildings",
            "CivicStructure",
          ].includes(t)
        )
      ) {
        placeJson = data;
        break;
      }
    } catch (e) {
      // ignore JSON parse error
    }
  }

  // 2. Place Name
  let placeName = (placeJson?.name || "").trim();
  if (!placeName) {
    const h1 =
      document.querySelector("h1.aon-heading-larger") ||
      document.querySelector("h1.place-title") ||
      document.querySelector("h1");
    if (h1 && h1.textContent.trim()) {
      placeName = h1.textContent.trim();
    }
  }
  if (!placeName && document.title) {
    placeName = document.title.replace(/\s*[-–—|]\s*Atlas Obscura.*$/i, "").trim();
  }

  // 3. Coordinates
  let lat = placeJson?.geo?.latitude ? parseFloat(placeJson.geo.latitude) : null;
  let lng = placeJson?.geo?.longitude ? parseFloat(placeJson.geo.longitude) : null;

  if (lat === null || lng === null) {
    const allDivs = document.querySelectorAll(
      ".aon-subtitle-smallest, .item-coordinates, div, span, p"
    );
    for (const el of allDivs) {
      const text = el.textContent.trim();
      const m = text.match(/^(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)$/);
      if (m) {
        lat = parseFloat(m[1]);
        lng = parseFloat(m[2]);
        break;
      }
    }
  }

  if (lat === null || lng === null) {
    const mapLink = document.querySelector('a[href*="maps.google.com"], a[href*="google.com/maps"]');
    if (mapLink) {
      const m = mapLink.href.match(/(?:q|query)=(-?\d+(?:\.\d+)?)(?:%2C|,)(-?\d+(?:\.\d+)?)/);
      if (m) {
        lat = parseFloat(m[1]);
        lng = parseFloat(m[2]);
      }
    }
  }

  // 4. Address fields
  const addrJson = placeJson?.address;
  const streetAddress = addrJson?.streetAddress || null;
  const city = addrJson?.addressLocality || null;
  const state = addrJson?.addressRegion || null;
  const country = addrJson?.addressCountry || null;
  const postalCode = addrJson?.postalCode || null;

  let fullAddress = "";
  if (streetAddress) fullAddress += streetAddress;
  if (city) fullAddress += (fullAddress ? ", " : "") + city;
  if (state) fullAddress += (fullAddress ? ", " : "") + state;
  if (postalCode) fullAddress += " " + postalCode;
  if (country) fullAddress += (fullAddress ? ", " : "") + country;

  if (!fullAddress) {
    const addrEl = document.querySelector("address");
    if (addrEl) {
      fullAddress = addrEl.textContent.replace(placeName, "").trim().replace(/\s+/g, " ");
    }
  }

  // 5. Official Website
  const sameAs = placeJson?.sameAs;
  let website = sanitizeOfficialWebsite((Array.isArray(sameAs) ? sameAs[0] : sameAs) || null);

  // 6. Image
  const ogImg = document.querySelector('meta[property="og:image"]')?.getAttribute("content");
  let imageUrl = placeJson?.image || ogImg || null;
  if (Array.isArray(imageUrl)) imageUrl = imageUrl[0];

  // 7. Description / Story
  let description = (placeJson?.description || "").trim();
  const bodyEl = document.querySelector(".place-body, .item-body, div[class*='place-body']");
  const fullBodyText = bodyEl ? bodyEl.textContent.trim().replace(/\s+/g, " ") : "";
  if (!description && fullBodyText) {
    description = fullBodyText.slice(0, 300) + "...";
  }

  // 8. Tags & Category
  const tags = [];
  const tagLinks = document.querySelectorAll(
    "a[href*='/categories/'], a[href*='/tags/'], .item-tags a, div.flex.flex-wrap.gap-4 a"
  );
  for (const t of tagLinks) {
    const tText = t.textContent.trim();
    if (tText && !tags.includes(tText) && tText.length < 35) {
      tags.push(tText);
    }
  }

  // POI Type mapping
  const lowerCat = (tags.join(" ") + " " + placeName).toLowerCase();
  let poiType = "site to see";
  if (
    lowerCat.includes("restaurant") ||
    lowerCat.includes("food") ||
    lowerCat.includes("bar") ||
    lowerCat.includes("wine") ||
    lowerCat.includes("cafe") ||
    lowerCat.includes("bakery") ||
    lowerCat.includes("dining")
  ) {
    poiType = "food/drink";
  } else if (
    lowerCat.includes("trail") ||
    lowerCat.includes("hike") ||
    lowerCat.includes("adventure") ||
    lowerCat.includes("experience")
  ) {
    poiType = "experience";
  } else if (
    lowerCat.includes("overlook") ||
    lowerCat.includes("viewpoint") ||
    lowerCat.includes("photo") ||
    lowerCat.includes("vista")
  ) {
    poiType = "photo location";
  } else if (
    lowerCat.includes("hotel") ||
    lowerCat.includes("lodging") ||
    lowerCat.includes("cabin") ||
    lowerCat.includes("resort")
  ) {
    poiType = "lodging";
  }

  // 9. Visit details from "Know Before You Go"
  let kbygText = "";
  const headings = Array.from(document.querySelectorAll("h2, h3, h4"));
  const kbygHeading = headings.find((h) => h.textContent.includes("Know Before You Go"));
  if (kbygHeading && kbygHeading.nextElementSibling) {
    kbygText = kbygHeading.nextElementSibling.textContent.trim();
  }

  let bestTimeToVisit = null;
  let bookingLeadTime = null;
  let costTier = null;
  let physicalEffort = poiType === "food/drink" ? "paved walk" : null;
  let environment = poiType === "food/drink" ? "Indoor" : null;

  if (kbygText) {
    const hoursMatch = kbygText.match(/(Lunch[^.\n]+|Dinner[^.\n]+|Open[^.\n]+|Hours[^.\n]+)/i);
    if (hoursMatch) {
      bestTimeToVisit = hoursMatch[0].trim();
    }
    if (/reservation/i.test(kbygText)) {
      bookingLeadTime = "reservations recommended";
    } else if (/walk-in/i.test(kbygText)) {
      bookingLeadTime = "walk-in ok";
    }
    if (/business casual|fine dining|upscale/i.test(kbygText)) {
      costTier = "$$$";
    } else if (/free|no admission/i.test(kbygText)) {
      costTier = "Free";
    }
  }

  return {
    isAtlasObscura: true,
    hasPlace: Boolean(placeName),
    placeName: placeName || "Atlas Obscura Place",
    lat,
    lng,
    address: fullAddress,
    city,
    state,
    country,
    postalCode,
    poiType,
    website,
    imageUrl,
    description,
    fullBodyText,
    tags,
    kbygText,
    bestTimeToVisit,
    bookingLeadTime,
    costTier,
    physicalEffort,
    environment,
  };
}

/**
 * Parses TripAdvisor place from URL and DOM.
 */
function parseTripAdvisorPlace() {
  const isTripAdvisor =
    window.location.hostname.includes("tripadvisor.") &&
    /(?:Attraction_Review|Restaurant_Review|Hotel_Review|VacationRental_Review)-/i.test(window.location.pathname);

  if (!isTripAdvisor) return null;

  let placeName = null;
  let city = null;
  let state = null;

  // Extract from URL: Reviews-<Place_Name>-<City>_<State_Or_Country>.html
  const urlMatch = window.location.pathname.match(/Reviews-([^_]+(?:_[^_]+)*?)-([^_]+(?:_[^_]+)*?)\.html/i);
  if (urlMatch) {
    placeName = decodeURIComponent(urlMatch[1].replace(/_/g, " ")).trim();
    const locPart = decodeURIComponent(urlMatch[2].replace(/_/g, " ")).trim();
    const locSplit = locPart.split(" ");
    if (locSplit.length >= 2) {
      city = locSplit.slice(0, -1).join(" ");
      state = locSplit[locSplit.length - 1];
    } else {
      city = locPart;
    }
  }

  const h1 =
    document.querySelector('h1[data-test-target="top-info-header"]') ||
    document.querySelector('h1.biGQs') ||
    document.querySelector('h1');
  if (h1 && h1.textContent.trim()) {
    placeName = h1.textContent.trim();
  }

  if (!placeName && document.title) {
    placeName = document.title.replace(/\s*[-–—|]\s*Tripadvisor.*$/i, "").trim();
  }

  let rating = 4;
  const ratingEl = document.querySelector('svg[aria-label*="bubbles"], span[aria-label*="of 5 bubbles"]');
  if (ratingEl) {
    const rm = ratingEl.getAttribute("aria-label")?.match(/(\d+(?:\.\d+)?)/);
    if (rm) rating = Math.round(parseFloat(rm[1]));
  }

  const tags = [];
  const catEls = document.querySelectorAll('a[href*="/Attractions-"], a[href*="/Restaurants-"], div[class*="header"] a');
  for (const el of catEls) {
    const t = el.textContent.trim();
    if (t && !tags.includes(t) && t.length < 35 && !t.toLowerCase().includes("see all")) {
      tags.push(t);
    }
  }

  let poiType = "site to see";
  if (window.location.pathname.includes("Restaurant_Review")) {
    poiType = "food/drink";
  } else if (window.location.pathname.includes("Hotel_Review")) {
    poiType = "lodging";
  } else if (tags.some((t) => /tour|hike|adventure|experience/i.test(t))) {
    poiType = "experience";
  } else if (tags.some((t) => /viewpoint|lookout|scenic/i.test(t))) {
    poiType = "photo location";
  }

  let duration = null;
  const durMatch = document.body.innerText.match(/Suggested duration:\s*([^\n.]+)/i);
  if (durMatch) {
    duration = durMatch[1].trim();
  }

  const descEl =
    document.querySelector('div[data-automation="WebPresentation_AttractionAbout"] div') ||
    document.querySelector('meta[property="og:description"]');
  const description = descEl ? (descEl.textContent || descEl.getAttribute("content") || "").trim() : null;

  const ogImg = document.querySelector('meta[property="og:image"]')?.getAttribute("content");
  const webLink = document.querySelector('a[href^="http"][aria-label*="Website"], a[data-encoded-url]');
  const website = webLink ? sanitizeOfficialWebsite(webLink.href) : null;

  return {
    isTripAdvisor: true,
    hasPlace: Boolean(placeName),
    placeName: placeName || "TripAdvisor Place",
    lat: null,
    lng: null,
    city,
    state,
    country: "US",
    rating,
    tags,
    poiType,
    estimatedDuration: duration,
    description,
    imageUrl: ogImg,
    website,
    searchQuery: `${placeName}, ${city || ""} ${state || ""}`.trim(),
  };
}

/**
 * Parses RoadsideAmerica story/attraction from URL and DOM.
 */
function parseRoadsideAmericaPlace() {
  const isRA =
    window.location.hostname.includes("roadsideamerica.com") &&
    /\/(?:story|attract|tip)\/\d+/i.test(window.location.pathname);

  if (!isRA) return null;

  const ogTitle = document.querySelector('meta[property="og:title"]')?.getAttribute("content") || document.title;
  let placeName = null;
  let city = null;
  let state = null;

  if (ogTitle) {
    const parts = ogTitle.split(",").map((s) => s.trim());
    if (parts.length >= 3) {
      placeName = parts[0];
      city = parts[1];
      state = parts[2];
    } else if (parts.length === 2) {
      placeName = parts[0];
      city = parts[1];
    } else {
      placeName = parts[0];
    }
  }

  const h1 = document.querySelector("h1");
  if (h1 && h1.textContent.trim()) {
    placeName = h1.textContent.trim();
  }

  const ogDesc = document.querySelector('meta[property="og:description"]')?.getAttribute("content");
  const storyEl = document.querySelector(".story, article, #story");
  const fullText = storyEl ? storyEl.textContent.trim().replace(/\s+/g, " ") : "";
  const description = ogDesc || (fullText ? fullText.slice(0, 300) + "..." : null);

  const ogImg = document.querySelector('meta[property="og:image"]')?.getAttribute("content");

  const tags = ["roadside", "quirky"];
  const lowerAll = (placeName + " " + (description || "")).toLowerCase();
  if (lowerAll.includes("cave") || lowerAll.includes("cavern")) tags.push("cave");
  if (lowerAll.includes("monument") || lowerAll.includes("statue")) tags.push("monument");
  if (lowerAll.includes("historic") || lowerAll.includes("history")) tags.push("historic");

  let effort = null;
  if (/stairs|flight of stairs/i.test(fullText)) effort = "stairs";
  let env = lowerAll.includes("cave") || lowerAll.includes("museum") ? "Indoor" : "Outdoor";

  return {
    isRoadsideAmerica: true,
    hasPlace: Boolean(placeName),
    placeName: placeName || "Roadside America Attraction",
    lat: null,
    lng: null,
    city,
    state,
    country: "US",
    tags,
    poiType: "site to see",
    description,
    imageUrl: ogImg,
    physicalEffort: effort,
    environment: env,
    searchQuery: `${placeName}, ${city || ""} ${state || ""}`.trim(),
  };
}

/**
 * Parses LocationScout photo spot from URL and DOM.
 */
function parseLocationScoutPlace() {
  const isLS =
    window.location.hostname.includes("locationscout.net") &&
    /\/[a-zA-Z0-9_-]+\/\d+-[a-zA-Z0-9_-]+/i.test(window.location.pathname);

  if (!isLS) return null;

  const ogTitle = document.querySelector('meta[property="og:title"]')?.getAttribute("content") || document.title;
  let placeName = null;
  let country = null;

  if (ogTitle) {
    const parts = ogTitle.split(",").map((s) => s.trim());
    placeName = parts[0];
    if (parts.length > 1) {
      country = parts[parts.length - 1];
    }
  }

  const h1 = document.querySelector("h1");
  if (h1 && h1.textContent.trim()) {
    const cleanH1 = h1.textContent.replace(country || "", "").trim();
    if (cleanH1) placeName = cleanH1;
  }

  let lat = null;
  let lng = null;
  const coordEl = document.querySelector("[data-lat][data-lng]");
  if (coordEl) {
    lat = parseFloat(coordEl.getAttribute("data-lat"));
    lng = parseFloat(coordEl.getAttribute("data-lng"));
  }

  const ogDesc = document.querySelector('meta[property="og:description"]')?.getAttribute("content");
  const ogImg = document.querySelector('meta[property="og:image"]')?.getAttribute("content");

  return {
    isLocationScout: true,
    hasPlace: Boolean(placeName),
    placeName: placeName || "LocationScout Spot",
    lat,
    lng,
    country,
    poiType: "photo location",
    tags: ["photo location", "photography", "scenic", "viewpoint"],
    description: ogDesc,
    imageUrl: ogImg,
    environment: "Outdoor",
    searchQuery: `${placeName}, ${country || ""}`.trim(),
  };
}

/**
 * Parses ShotHotspot photography location from URL and DOM.
 */
function parseShotHotspotPlace() {
  const isSH =
    window.location.hostname.includes("shothotspot.com") &&
    /\/hotspot\/[^\s/]+\/[^\s/]+/i.test(window.location.pathname);

  if (!isSH) return null;

  let placeName = null;
  let lat = null;
  let lng = null;
  let country = null;

  const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of jsonLdScripts) {
    try {
      const data = JSON.parse(script.textContent || "{}");
      if (data["@type"] === "Place") {
        placeName = data.name;
        if (data.geo) {
          lat = parseFloat(data.geo.latitude);
          lng = parseFloat(data.geo.longitude);
        }
        if (data.address?.addressCountry) {
          country = data.address.addressCountry;
        }
        break;
      }
    } catch (e) {
      // ignore
    }
  }

  if (!placeName) {
    const h1 = document.querySelector("h1");
    if (h1 && h1.textContent.trim()) {
      placeName = h1.textContent.trim();
    }
  }

  const ogDesc = document.querySelector('meta[property="og:description"]')?.getAttribute("content");
  const ogImg = document.querySelector('meta[property="og:image"]')?.getAttribute("content");

  return {
    isShotHotspot: true,
    hasPlace: Boolean(placeName),
    placeName: placeName || "ShotHotspot Location",
    lat,
    lng,
    country,
    poiType: "photo location",
    tags: ["photo location", "photography", "scenic", "viewpoint"],
    description: ogDesc,
    imageUrl: ogImg,
    environment: "Outdoor",
    searchQuery: `${placeName}, ${country || ""}`.trim(),
  };
}

/**
 * Generic fallback parser when no text is selected on an unrecognized site.
 * Inspects JSON-LD, meta tags, headers, and primary content.
 */
function parseGenericPageFallback() {
  const title = document.title || "";
  let placeName = null;
  let lat = null;
  let lng = null;
  let city = null;
  let state = null;
  let country = null;
  let description = null;
  let website = null;
  let imageUrl = null;
  const tags = [];

  // 1. Check application/ld+json for Place / TouristAttraction / LocalBusiness
  const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of jsonLdScripts) {
    try {
      const data = JSON.parse(script.textContent || "{}");
      const list = Array.isArray(data) ? data : [data];
      for (const item of list) {
        const types = Array.isArray(item["@type"]) ? item["@type"] : [item["@type"]];
        if (
          types.some((t) =>
            [
              "Place",
              "TouristAttraction",
              "LocalBusiness",
              "Park",
              "Museum",
              "Restaurant",
              "Hotel",
              "LandmarksOrHistoricalBuildings",
              "CivicStructure",
            ].includes(t)
          )
        ) {
          if (item.name) placeName = String(item.name).trim();
          if (item.description) description = String(item.description).trim();
          if (item.geo) {
            lat = parseFloat(item.geo.latitude);
            lng = parseFloat(item.geo.longitude);
          }
          if (item.address) {
            city = item.address.addressLocality || null;
            state = item.address.addressRegion || null;
            country = item.address.addressCountry || null;
          }
          if (item.image) {
            imageUrl = Array.isArray(item.image) ? item.image[0] : item.image;
          }
          if (item.url) website = sanitizeOfficialWebsite(item.url);
          break;
        }
      }
      if (placeName) break;
    } catch (e) {
      // ignore JSON parse error
    }
  }

  // 2. Geotags: geo.position or ICBM
  if (lat === null || lng === null) {
    const geoPos = document.querySelector('meta[name="geo.position"]')?.getAttribute("content");
    const icbm = document.querySelector('meta[name="ICBM"]')?.getAttribute("content");
    const posStr = geoPos || icbm;
    if (posStr) {
      const m = posStr.match(/(-?\d+\.\d+)[,;\s]+(-?\d+\.\d+)/);
      if (m) {
        lat = parseFloat(m[1]);
        lng = parseFloat(m[2]);
      }
    }
  }

  // 3. Document heading & meta fallbacks
  if (!placeName) {
    const h1 = document.querySelector("h1");
    if (h1 && h1.textContent.trim()) {
      placeName = h1.textContent.trim();
    } else {
      placeName = title.split(/[-–—|]/)[0].trim();
    }
  }

  if (!description) {
    const metaDesc =
      document.querySelector('meta[property="og:description"]')?.getAttribute("content") ||
      document.querySelector('meta[name="description"]')?.getAttribute("content");
    if (metaDesc) description = metaDesc.trim();
  }

  if (!imageUrl) {
    imageUrl = document.querySelector('meta[property="og:image"]')?.getAttribute("content") || null;
  }

  // Extract clean text snippet from main article container
  const mainEl =
    document.querySelector('article, main, #content, .content, .post, [role="main"]') || document.body;
  const rawBodyText = mainEl ? mainEl.innerText.replace(/\s+/g, " ").trim() : "";
  const snippet = rawBodyText.slice(0, 1500);

  return {
    isGenericFallback: true,
    hasPlace: Boolean(placeName),
    placeName,
    lat,
    lng,
    city,
    state,
    country,
    description: description || (snippet ? snippet.slice(0, 300) + "..." : null),
    fullBodyText: snippet,
    imageUrl,
    website,
    tags,
  };
}

/**
 * Primary capture orchestration triggered by shortcut or context menu.
 */
async function initiateCapture(initialText = null) {
  console.log("%c[Vistarae] 🚀 Capture initiated on:", "color: #0d9488; font-weight: bold;", window.location.href);
  let selection = initialText || window.getSelection().toString().trim();
  const title = document.title || "";
  const url = window.location.href;
  const ogImageMeta = document.querySelector('meta[property="og:image"]');
  let ogImageUrl = ogImageMeta ? ogImageMeta.getAttribute("content") : null;
  const isGoogleMapsHost = window.location.hostname.includes("google.") && window.location.pathname.includes("/maps");
  if (isGoogleMapsHost || isMapOrPlaceholderImageUrl(ogImageUrl)) {
    ogImageUrl = null;
  }

  const gmapsInfo = parseGoogleMapsPlace();
  const googleSearchInfo = parseGoogleSearchPlace();
  const aoInfo = parseAtlasObscuraPlace();
  const taInfo = parseTripAdvisorPlace();
  const raInfo = parseRoadsideAmericaPlace();
  const lsInfo = parseLocationScoutPlace();
  const shInfo = parseShotHotspotPlace();

  // Also check if selection contains an Atlas Obscura URL from another site
  const aoUrlMatch = (selection || "").match(/https?:\/\/(?:www\.)?atlasobscura\.com\/places\/([a-zA-Z0-9_-]+)/i);
  const isAoUrlSelection = Boolean(aoUrlMatch && !aoInfo);

  let activePlatform = null;
  if (gmapsInfo && gmapsInfo.isGoogleMaps) activePlatform = gmapsInfo;
  else if (googleSearchInfo && googleSearchInfo.isGoogleSearch) activePlatform = googleSearchInfo;
  else if (aoInfo && aoInfo.isAtlasObscura) activePlatform = aoInfo;
  else if (taInfo && taInfo.isTripAdvisor) activePlatform = taInfo;
  else if (raInfo && raInfo.isRoadsideAmerica) activePlatform = raInfo;
  else if (lsInfo && lsInfo.isLocationScout) activePlatform = lsInfo;
  else if (shInfo && shInfo.isShotHotspot) activePlatform = shInfo;

  console.log("[Vistarae] Detected Platform:", activePlatform ? activePlatform.isGoogleSearch ? "Google Search Entity" : activePlatform.placeName : "Generic Page");

  // If no text was highlighted, check platform or use generic page fallback
  if (!selection) {
    if (activePlatform) {
      if (!activePlatform.hasPlace) {
        showToast("No travel site or location could be detected on this page.", true);
        return;
      }
      selection = activePlatform.description || activePlatform.fullBodyText || activePlatform.placeName || "";
      if (activePlatform.imageUrl && !isMapOrPlaceholderImageUrl(activePlatform.imageUrl)) {
        ogImageUrl = activePlatform.imageUrl;
      }
    } else {
      const pageFallback = parseGenericPageFallback();
      activePlatform = pageFallback;
      selection = pageFallback.fullBodyText || pageFallback.description || pageFallback.placeName || "";
      if (pageFallback.imageUrl && !isMapOrPlaceholderImageUrl(pageFallback.imageUrl)) {
        ogImageUrl = pageFallback.imageUrl;
      }
    }
  } else if (activePlatform) {
    if (activePlatform.imageUrl && !isMapOrPlaceholderImageUrl(activePlatform.imageUrl)) {
      ogImageUrl = activePlatform.imageUrl;
    }
  }

  const resolvedImageUrl =
    (!isMapOrPlaceholderImageUrl(ogImageUrl) ? ogImageUrl : null) ||
    (!isMapOrPlaceholderImageUrl(activePlatform?.imageUrl) ? activePlatform.imageUrl : null) ||
    null;

  const payload = {
    selected_text: selection,
    page_title: activePlatform?.placeName || title,
    page_url: isAoUrlSelection ? aoUrlMatch[0] : url,
    og_image_url: resolvedImageUrl,
    latitude: activePlatform?.lat ?? null,
    longitude: activePlatform?.lng ?? null,
    place_name: activePlatform?.placeName || null,
    category: activePlatform?.poiType || activePlatform?.category || null,
    website: activePlatform?.website || null,
    phone_number: activePlatform?.phoneNumber || null,
    city: activePlatform?.city || null,
    state: activePlatform?.state || null,
    country: activePlatform?.country || null,
    postal_code: activePlatform?.postalCode || null,
    category_tags: activePlatform?.tags || [],
    physical_effort: activePlatform?.physicalEffort || null,
    booking_lead_time: activePlatform?.bookingLeadTime || null,
    indoor_outdoor: activePlatform?.environment || null,
    estimated_duration: activePlatform?.estimatedDuration || null,
    cost_tier: activePlatform?.costTier || null,
    best_time_to_visit: activePlatform?.bestTimeToVisit || null,
    source_type: activePlatform?.isAtlasObscura
      ? "Atlas Obscura"
      : activePlatform?.isTripAdvisor
      ? "TripAdvisor"
      : activePlatform?.isRoadsideAmerica
      ? "Roadside America"
      : activePlatform?.isLocationScout
      ? "LocationScout"
      : activePlatform?.isShotHotspot
      ? "ShotHotspot"
      : activePlatform?.isGoogleMaps
      ? "Google Maps"
      : activePlatform?.isGoogleSearch
      ? "Google Search"
      : "Web Page",
  };

  console.log("[Vistarae] Prepared extraction payload:", payload);

  // Check auth first
  sendExtensionMessage({ action: "GET_AUTH" }, (auth) => {
    if (!auth || !auth.isAuthenticated) {
      console.log("[Vistarae] User not authenticated. Showing auth modal.");
      renderAuthModal(payload);
    } else {
      console.log("[Vistarae] User authenticated as:", auth.user?.email);
      executeExtractionAndCheck(payload, auth.user);
    }
  });
}

/**
 * Calls backend /extract-and-check with error & auth recovery.
 */
function executeExtractionAndCheck(payload, currentUser) {
  showLoadingModal();

  console.log("[Vistarae] Dispatching EXTRACT_AND_CHECK to background worker...");
  sendExtensionMessage(
    { action: "EXTRACT_AND_CHECK", payload },
    (response) => {
      console.log("[Vistarae] Received backend response:", response);

      if (chrome.runtime.lastError || !response || !response.success) {
        removeModal();
        if (response?.unauthorized) {
          showToast("Session expired. Please sign in again.", true);
          renderAuthModal(payload);
          return;
        }
        const errorMsg = response?.error || chrome.runtime.lastError?.message || "Failed to reach Vistarae backend";
        showToast(errorMsg, true);
        return;
      }

      // Check if location could not be determined
      const resData = response.data;
      if (
        resData?.location_detected === false ||
        (!resData?.latitude &&
          !resData?.longitude &&
          !resData?.candidate?.iptc_city &&
          !resData?.candidate?.iptc_province_state &&
          !resData?.candidate?.search_address_query)
      ) {
        console.warn("[Vistarae] Location not automatically detected. Proceeding to editor without coordinates:", resData);
      }

      console.log("[Vistarae] Rendering capture editor with candidate:", resData.candidate);
      renderCaptureEditor(resData, payload, currentUser);
    }
  );
}


const TAGS_CACHE_KEY = "vistarae_tags_cache";
const LISTS_CACHE_KEY = "vistarae_lists_cache";
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

async function getCachedItem(key) {
  try {
    const res = await chrome.storage.local.get(key);
    const entry = res[key];
    if (entry && entry.timestamp && Date.now() - entry.timestamp < CACHE_TTL_MS) {
      return entry.data;
    }
  } catch (e) {
    // ignore cache read errors
  }
  return null;
}

async function setCachedItem(key, data) {
  try {
    await chrome.storage.local.set({
      [key]: { data, timestamp: Date.now() },
    });
  } catch (e) {
    // ignore cache write errors
  }
}

const NPS_KEYWORDS = [
  "national park", "national monument", "national battlefield", "national military park",
  "national historic site", "national historical park", "national recreation area",
  "national seashore", "national lakeshore", "national preserve", "national memorial",
  "national river", "national parkway", "national scenic trail", "national heritage area",
  "national park service"
];

function isNpsLocation(text) {
  if (!text) return false;
  const lower = String(text).toLowerCase();
  return lower.includes("nps.gov") || NPS_KEYWORDS.some((kw) => lower.includes(kw));
}

/**
 * Renders the interactive editor modal.
 */
async function renderCaptureEditor(data, originalRequest, currentUser = null) {
  const root = getOrCreateShadowRoot();
  const existing = root.querySelector(".vistarae-backdrop");
  if (existing) existing.remove();

  const cand = data.candidate || {};
  let currentRating = cand.personal_rating || 3;
  let selectedListIds = new Set();
  let parentPoiId = data.nearby_parent?.id || null;

  // Collision Banner Construction
  let bannerClass = "status-unique";
  let bannerIcon = "🟢";
  let bannerText = "Unique Location — No collision detected within 500ft in your collection.";
  let diffHtml = "";

  if (data.collision_status === "POTENTIAL_DUPLICATE" && data.matched_poi) {
    bannerClass = "status-duplicate";
    bannerIcon = "🟡";
    bannerText = `Potential Duplicate: "${escapeHtml(data.matched_poi.name)}" is in your records ${data.matched_poi.distance_meters}m away (${Math.round(data.matched_poi.name_similarity * 100)}% similarity).`;
    diffHtml = `
      <div class="vistarae-diff-card">
        <strong>Existing Record:</strong> ${escapeHtml(data.matched_poi.name)} (${escapeHtml(data.matched_poi.poi_type)})<br/>
        <span style="color: #64748b;">${escapeHtml(data.matched_poi.description || "No description")}</span>
      </div>
    `;
  } else if (data.collision_status === "NEARBY_PARENT" && data.nearby_parent) {
    bannerClass = "status-parent";
    bannerIcon = "🔵";
    bannerText = `Nearby Macro-Site: Found "${escapeHtml(data.nearby_parent.name)}" in your collection. Suggest nesting as child POI.`;
  }

  // Tag Management with Caching & NPS auto-tagging
  const selectedTags = new Set(cand.category_tags || []);
  if (
    isNpsLocation(cand.name) ||
    isNpsLocation(cand.website_official) ||
    isNpsLocation(originalRequest.website) ||
    isNpsLocation(cand.description) ||
    isNpsLocation(originalRequest.page_title) ||
    isNpsLocation(originalRequest.page_url) ||
    isNpsLocation(originalRequest.selected_text) ||
    isNpsLocation(originalRequest.category)
  ) {
    selectedTags.add("NPS");
  }

  // Initialize available tags
  const allAvailableTags = new Set([
    "NPS", "scenic", "viewpoint", "hiking", "waterfall", "sunset", "sunrise",
    "wildlife", "photography", "historic", "nature", "beach", "museum",
    "ship", "military", "airplane", "aviation", "space", "island", "monument",
    "memorial", "lighthouse", "castle", "bridge", "mountain", "canyon",
    "cave", "park", "food", "overlook", "trail", "lodging"
  ]);

  (data.available_tags || []).forEach((t) => allAvailableTags.add(t));
  selectedTags.forEach((t) => allAvailableTags.add(t));

  // Merge with cached tags if available
  const cachedTags = await getCachedItem(TAGS_CACHE_KEY);
  if (cachedTags && Array.isArray(cachedTags)) {
    cachedTags.forEach((t) => allAvailableTags.add(t));
  }
  setCachedItem(TAGS_CACHE_KEY, Array.from(allAvailableTags));

  // List Management with Caching
  let availableLists = data.available_lists || [];
  if (availableLists.length === 0) {
    const cachedLists = await getCachedItem(LISTS_CACHE_KEY);
    if (cachedLists && Array.isArray(cachedLists) && cachedLists.length > 0) {
      availableLists = cachedLists;
    }
  } else {
    setCachedItem(LISTS_CACHE_KEY, availableLists);
  }

  const userGreeting = currentUser?.email ? escapeHtml(currentUser.email) : "My Collection";
  const rawImage = cand.primary_image_url || originalRequest.og_image_url || "";
  const initialImageUrl = isMapOrPlaceholderImageUrl(rawImage) ? "" : rawImage;
  const initialWebsite = sanitizeOfficialWebsite(cand.website_official || originalRequest.website) || "";
  const initialPhone = cand.phone_number || originalRequest.phone_number || "";

  const backdrop = document.createElement("div");
  backdrop.className = "vistarae-backdrop";

  backdrop.innerHTML = `
    <div class="vistarae-modal">
      <div class="vistarae-header">
        <div class="vistarae-title-wrap">
          <div class="vistarae-logo-icon">V</div>
          <div>
            <h2 class="vistarae-title">Capture to Vistarae</h2>
            <div class="vistarae-user-pill">
              <span>👤 ${userGreeting}</span>
              <button class="vistarae-logout-btn" id="vistarae-browse-db" style="margin-left: 6px; color: #0d9488; font-weight: 600;">Browse POIs</button>
              <button class="vistarae-logout-btn" id="vistarae-logout">Sign Out</button>
            </div>

          </div>
        </div>
        <button class="vistarae-close-btn" id="vistarae-modal-close">&times;</button>
      </div>

      <div class="vistarae-status-banner ${bannerClass}">
        <span>${bannerIcon}</span>
        <span>${bannerText}</span>
      </div>
      ${diffHtml}

      <div class="vistarae-body">
        <div class="vistarae-field-group">
          <label class="vistarae-label">Point of Interest Name</label>
          <input type="text" class="vistarae-input" id="v-name" value="${escapeHtml(cand.name || originalRequest.place_name || "")}" />
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Parent Macro-Site (optional)</label>
          <select class="vistarae-select" id="v-parent-poi">
            <option value="">None (Top-Level Site)</option>
            ${(data.available_parents || []).map((p) => `
              <option value="${p.id}" ${parentPoiId === p.id ? "selected" : ""}>
                ${escapeHtml(p.name)} (${escapeHtml(p.poi_type)})
              </option>
            `).join("")}
          </select>
        </div>

        <div class="vistarae-grid-2">
          <div class="vistarae-field-group">
            <label class="vistarae-label">POI Type</label>
            <select class="vistarae-select" id="v-type">
              <option value="photo location" ${cand.poi_type === "photo location" ? "selected" : ""}>Photo Location</option>
              <option value="site to see" ${cand.poi_type === "site to see" ? "selected" : ""}>Site to See</option>
              <option value="experience" ${cand.poi_type === "experience" ? "selected" : ""}>Experience</option>
              <option value="food/drink" ${cand.poi_type === "food/drink" ? "selected" : ""}>Food / Drink</option>
              <option value="lodging" ${cand.poi_type === "lodging" ? "selected" : ""}>Lodging</option>
              <option value="transit" ${cand.poi_type === "transit" ? "selected" : ""}>Transit</option>
            </select>
          </div>

          <div class="vistarae-field-group">
            <label class="vistarae-label">Personal Rating</label>
            <div class="vistarae-rating-stars" id="v-stars">
              ${[1, 2, 3, 4, 5].map((num) => `
                <span class="vistarae-star ${num <= currentRating ? "active" : ""}" data-val="${num}">★</span>
              `).join("")}
            </div>
          </div>
        </div>

        <div class="vistarae-grid-2">
          <div class="vistarae-field-group">
            <label class="vistarae-label">Latitude</label>
            <input type="number" step="any" class="vistarae-input" id="v-lat" value="${data.latitude !== null && data.latitude !== undefined ? data.latitude : ""}" placeholder="e.g. 37.7275" />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">Longitude</label>
            <input type="number" step="any" class="vistarae-input" id="v-lng" value="${data.longitude !== null && data.longitude !== undefined ? data.longitude : ""}" placeholder="e.g. -119.5742" />
          </div>
        </div>

        <div class="vistarae-grid-2">
          <div class="vistarae-field-group">
            <label class="vistarae-label">Official Website</label>
            <input type="url" class="vistarae-input" id="v-website" value="${escapeHtml(initialWebsite)}" placeholder="https://..." />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">Phone Number</label>
            <input type="tel" class="vistarae-input" id="v-phone" value="${escapeHtml(initialPhone)}" placeholder="(555) 123-4567" />
          </div>
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Primary Image URL</label>
          <div class="vistarae-image-row">
            <img id="v-image-preview" class="vistarae-image-preview" src="${escapeHtml(initialImageUrl)}" alt="Preview" style="${initialImageUrl ? 'display: block;' : 'display: none;'}" />
            <input type="url" class="vistarae-input" id="v-image-url" value="${escapeHtml(initialImageUrl)}" placeholder="https://image-url... (or leave blank)" style="flex: 1;" />
          </div>
        </div>

        <div class="vistarae-field-group">
          <div class="vistarae-visited-header">
            <label class="vistarae-label" for="v-visit-date" style="margin: 0; display: flex; align-items: center; gap: 6px;">
              <span>🗓️</span>
              <span style="font-weight: 600;">I have visited this place</span>
              <span class="vistarae-sublabel">(set date visited)</span>
            </label>
            <div class="vistarae-date-actions">
              <button type="button" class="vistarae-date-btn" id="v-visit-today-btn" title="Set date to Today">Today</button>
              <button type="button" class="vistarae-date-btn vistarae-date-clear-btn" id="v-visit-clear-btn" title="Clear visit date">Clear</button>
            </div>
          </div>
          <div class="vistarae-date-input-wrap">
            <input type="date" class="vistarae-input" id="v-visit-date" />
          </div>
          <div style="margin-top: 6px;">
            <label style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; cursor: pointer; user-select: none;">
              <input type="checkbox" id="v-visit-again" style="width: 14px; height: 14px; cursor: pointer; accent-color: #0d9488;">
              <span style="font-weight: 500;">🔄 Visit Again</span>
            </label>
          </div>
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Description & Highlights</label>
          <textarea class="vistarae-textarea" id="v-desc" placeholder="Narrative description and visit highlights...">${escapeHtml(cand.description || originalRequest.selected_text || "")}</textarea>
        </div>

        <div class="vistarae-grid-3">
          <div class="vistarae-field-group">
            <label class="vistarae-label">City / Town</label>
            <input type="text" class="vistarae-input" id="v-city" value="${escapeHtml(cand.iptc_city || originalRequest.city || "")}" />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">State / Province</label>
            <input type="text" class="vistarae-input" id="v-state" value="${escapeHtml(cand.iptc_province_state || originalRequest.state || "")}" />
          </div>
          <div class="vistarae-field-group">
            <label class="vistarae-label">Country Code</label>
            <input type="text" class="vistarae-input" id="v-country" maxlength="2" value="${escapeHtml(cand.iptc_country_code || originalRequest.country || "US")}" />
          </div>
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Category Tags (click to toggle)</label>
          <div class="vistarae-tags-cloud" id="v-tags-cloud"></div>
          <div class="vistarae-add-tag-row">
            <input type="text" class="vistarae-input" id="v-new-tag-name" placeholder="+ Add custom tag..." style="flex: 1;" />
            <button type="button" class="vistarae-btn vistarae-btn-secondary" id="v-add-tag-btn">Add</button>
          </div>
        </div>

        <div class="vistarae-field-group">
          <label class="vistarae-label">Add to My Lists</label>
          <div class="vistarae-lists-container" id="v-lists-list">
            ${availableLists.map((lst) => `
              <div class="vistarae-list-tag" data-id="${lst.id}">
                <span>+</span> <span>${escapeHtml(lst.title)}</span>
              </div>
            `).join("")}
          </div>
          <div class="vistarae-add-list-row">
            <input type="text" class="vistarae-input" id="v-new-list-title" placeholder="+ Create new list..." />
            <button type="button" class="vistarae-btn vistarae-btn-secondary" id="v-add-list-btn">Add</button>
          </div>
        </div>

        <!-- Visit Details Section at Bottom -->
        <div class="vistarae-section" id="v-visit-details-section">
          <div class="vistarae-section-title">
            <span>🗓️</span> <span>Visit Details</span>
          </div>

          <div class="vistarae-grid-3">
            <div class="vistarae-field-group">
              <label class="vistarae-label">Physical Effort</label>
              <input type="text" class="vistarae-input" id="v-effort" value="${escapeHtml(cand.physical_effort || originalRequest.physical_effort || "")}" placeholder="e.g. drive-up, paved walk, moderate hike" />
            </div>
            <div class="vistarae-field-group">
              <label class="vistarae-label">Environment</label>
              <select class="vistarae-select" id="v-indoor">
                <option value="" ${!(cand.indoor_outdoor || originalRequest.indoor_outdoor) ? "selected" : ""}>Not specified</option>
                <option value="Outdoor" ${(cand.indoor_outdoor || originalRequest.indoor_outdoor) === "Outdoor" ? "selected" : ""}>Outdoor</option>
                <option value="Indoor" ${(cand.indoor_outdoor || originalRequest.indoor_outdoor) === "Indoor" ? "selected" : ""}>Indoor</option>
                <option value="Mixed" ${(cand.indoor_outdoor || originalRequest.indoor_outdoor) === "Mixed" ? "selected" : ""}>Mixed</option>
              </select>
            </div>
            <div class="vistarae-field-group">
              <label class="vistarae-label">Lead Time</label>
              <input type="text" class="vistarae-input" id="v-lead" value="${escapeHtml(cand.booking_lead_time || originalRequest.booking_lead_time || "")}" placeholder="e.g. walk-in ok, 1-3 days ahead" />
            </div>
          </div>

          <div class="vistarae-grid-3">
            <div class="vistarae-field-group">
              <label class="vistarae-label">Estimated Duration</label>
              <input type="text" class="vistarae-input" id="v-duration" value="${escapeHtml(cand.estimated_duration || originalRequest.estimated_duration || "")}" placeholder="e.g. 1-2 hours" />
            </div>
            <div class="vistarae-field-group">
              <label class="vistarae-label">Cost Tier</label>
              <input type="text" class="vistarae-input" id="v-cost" value="${escapeHtml(cand.cost_tier || originalRequest.cost_tier || "")}" placeholder="e.g. Free, $, $$" />
            </div>
            <div class="vistarae-field-group">
              <label class="vistarae-label">Best Time to Visit</label>
              <input type="text" class="vistarae-input" id="v-best-time" value="${escapeHtml(cand.best_time_to_visit || originalRequest.best_time_to_visit || "")}" placeholder="e.g. Golden Hour, Sunset" />
            </div>
          </div>
        </div>
      </div>

      <div class="vistarae-footer">
        <button class="vistarae-btn vistarae-btn-secondary" id="vistarae-cancel-btn">Cancel</button>
        <button class="vistarae-btn vistarae-btn-primary" id="vistarae-save-btn">Save to Vistarae</button>
      </div>
    </div>
  `;

  root.appendChild(backdrop);

  // Close & Cancel listeners
  backdrop.querySelector("#vistarae-modal-close").addEventListener("click", removeModal);
  backdrop.querySelector("#vistarae-cancel-btn").addEventListener("click", removeModal);

  // Browse POIs listener
  const browseBtn = backdrop.querySelector("#vistarae-browse-db");
  if (browseBtn) {
    browseBtn.addEventListener("click", () => {
      sendExtensionMessage({ action: "OPEN_BROWSER" }, () => {
        removeModal();
      });
    });
  }

  // Logout listener
  const logoutBtn = backdrop.querySelector("#vistarae-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      sendExtensionMessage({ action: "LOGOUT" }, () => {
        removeModal();
        showToast("Signed out successfully.");
      });
    });
  }


  // Parent POI dropdown change listener
  const parentPoiSelect = backdrop.querySelector("#v-parent-poi");
  if (parentPoiSelect) {
    parentPoiSelect.addEventListener("change", (e) => {
      parentPoiId = e.target.value || null;
    });
  }

  // Visited date handlers
  const visitDateInput = backdrop.querySelector("#v-visit-date");
  const clearVisitBtn = backdrop.querySelector("#v-visit-clear-btn");
  if (clearVisitBtn && visitDateInput) {
    clearVisitBtn.addEventListener("click", (e) => {
      e.preventDefault();
      visitDateInput.value = "";
    });
  }

  const todayVisitBtn = backdrop.querySelector("#v-visit-today-btn");
  if (todayVisitBtn && visitDateInput) {
    todayVisitBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const now = new Date();
      const yyyy = now.getFullYear();
      const mm = String(now.getMonth() + 1).padStart(2, "0");
      const dd = String(now.getDate()).padStart(2, "0");
      visitDateInput.value = `${yyyy}-${mm}-${dd}`;
    });
  }

  // Image Preview handlers
  const imgInput = backdrop.querySelector("#v-image-url");
  const imgPreview = backdrop.querySelector("#v-image-preview");
  const updateImgPreview = () => {
    const src = imgInput.value.trim();
    if (src) {
      imgPreview.src = src;
      imgPreview.style.display = "block";
    } else {
      imgPreview.style.display = "none";
    }
  };
  imgPreview.onerror = () => {
    imgPreview.style.display = "none";
  };
  imgPreview.onload = () => {
    imgPreview.style.display = "block";
  };
  if (imgInput.value.trim()) {
    imgPreview.style.display = "block";
  }
  imgInput.addEventListener("input", updateImgPreview);

  // Star rating click handler
  const starContainer = backdrop.querySelector("#v-stars");
  starContainer.addEventListener("click", (e) => {
    const star = e.target.closest(".vistarae-star");
    if (star) {
      currentRating = parseInt(star.getAttribute("data-val"), 10);
      starContainer.querySelectorAll(".vistarae-star").forEach((s) => {
        const val = parseInt(s.getAttribute("data-val"), 10);
        s.classList.toggle("active", val <= currentRating);
      });
    }
  });

  // Tag Cloud Rendering & Interaction
  const tagsCloud = backdrop.querySelector("#v-tags-cloud");
  const renderTagsCloud = () => {
    tagsCloud.innerHTML = "";
    const sortedTags = Array.from(allAvailableTags).sort((a, b) => {
      if (a === "NPS") return -1;
      if (b === "NPS") return 1;
      return a.localeCompare(b);
    });

    sortedTags.forEach((tag) => {
      const isSelected = selectedTags.has(tag);
      const pill = document.createElement("div");
      pill.className = `vistarae-tag-pill ${isSelected ? "active" : ""}`;
      pill.setAttribute("data-tag", tag);
      pill.innerHTML = `<span>${isSelected ? "✓" : "+"}</span> <span>${escapeHtml(tag)}</span>`;
      tagsCloud.appendChild(pill);
    });
  };

  renderTagsCloud();

  tagsCloud.addEventListener("click", (e) => {
    const pill = e.target.closest(".vistarae-tag-pill");
    if (pill) {
      const tag = pill.getAttribute("data-tag");
      if (selectedTags.has(tag)) {
        selectedTags.delete(tag);
      } else {
        selectedTags.add(tag);
      }
      renderTagsCloud();
    }
  });

  // Add Custom Tag Handler
  const newTagInput = backdrop.querySelector("#v-new-tag-name");
  const addTagBtn = backdrop.querySelector("#v-add-tag-btn");
  const handleAddNewTag = () => {
    const raw = newTagInput.value.trim();
    if (!raw) return;
    const cleanTag = raw.replace(/[^\w\s-]/g, "").trim();
    if (!cleanTag) return;

    allAvailableTags.add(cleanTag);
    selectedTags.add(cleanTag);
    renderTagsCloud();
    newTagInput.value = "";

    // Persist custom tag to backend and update cache
    sendExtensionMessage({ action: "CREATE_TAG", payload: { name: cleanTag } });
    setCachedItem(TAGS_CACHE_KEY, Array.from(allAvailableTags));
  };
  addTagBtn.addEventListener("click", handleAddNewTag);
  newTagInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddNewTag();
    }
  });

  // List tags click handler
  const listContainer = backdrop.querySelector("#v-lists-list");
  listContainer.addEventListener("click", (e) => {
    const tag = e.target.closest(".vistarae-list-tag");
    if (tag) {
      const listId = tag.getAttribute("data-id");
      if (selectedListIds.has(listId)) {
        selectedListIds.delete(listId);
        tag.classList.remove("selected");
        tag.querySelector("span:first-child").textContent = "+";
      } else {
        selectedListIds.add(listId);
        tag.classList.add("selected");
        tag.querySelector("span:first-child").textContent = "✓";
      }
    }
  });

  // Create new list dynamically
  const newListInput = backdrop.querySelector("#v-new-list-title");
  const addListBtn = backdrop.querySelector("#v-add-list-btn");
  const handleAddNewList = () => {
    const title = newListInput.value.trim();
    if (!title) return;

    sendExtensionMessage(
      { action: "CREATE_LIST", payload: { title, is_trip: false } },
      (res) => {
        if (res && res.success && res.data) {
          const newList = res.data;
          const tag = document.createElement("div");
          tag.className = "vistarae-list-tag selected";
          tag.setAttribute("data-id", newList.id);
          tag.innerHTML = `<span>✓</span> <span>${escapeHtml(newList.title)}</span>`;
          listContainer.appendChild(tag);
          selectedListIds.add(newList.id);
          newListInput.value = "";

          // Update cached lists
          getCachedItem(LISTS_CACHE_KEY).then((cached) => {
            const updated = cached ? [...cached, newList] : [newList];
            setCachedItem(LISTS_CACHE_KEY, updated);
          });
        } else {
          showToast(res?.error || "Failed to create list", true);
        }
      }
    );
  };
  addListBtn.addEventListener("click", handleAddNewList);
  newListInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddNewList();
    }
  });

  // Save handler
  const saveBtn = backdrop.querySelector("#vistarae-save-btn");
  saveBtn.addEventListener("click", () => {
    saveBtn.disabled = true;
    saveBtn.textContent = "Saving...";

    const latText = backdrop.querySelector("#v-lat")?.value?.trim();
    const lngText = backdrop.querySelector("#v-lng")?.value?.trim();
    const latParsed = latText ? parseFloat(latText) : null;
    const lngParsed = lngText ? parseFloat(lngText) : null;
    const finalLat = (latParsed !== null && !isNaN(latParsed)) ? latParsed : (data.latitude ?? null);
    const finalLng = (lngParsed !== null && !isNaN(lngParsed)) ? lngParsed : (data.longitude ?? null);

    const visitDateVal = backdrop.querySelector("#v-visit-date")?.value?.trim() || null;
    const isVisited = Boolean(visitDateVal);
    const parentVal = backdrop.querySelector("#v-parent-poi").value;
    const rawSavedImg = backdrop.querySelector("#v-image-url").value.trim() || null;
    const finalSavedImg = isMapOrPlaceholderImageUrl(rawSavedImg) ? null : rawSavedImg;

    const savePayload = {
      name: backdrop.querySelector("#v-name").value.trim(),
      name_aliases: cand.name_aliases || [],
      poi_type: backdrop.querySelector("#v-type").value,
      personal_rating: currentRating,
      description: backdrop.querySelector("#v-desc").value.trim(),
      category_tags: Array.from(selectedTags),
      visited: isVisited,
      visit_date: visitDateVal,
      visit_again: Boolean(backdrop.querySelector("#v-visit-again")?.checked),
      latitude: finalLat,
      longitude: finalLng,
      geofence_radius_ft: 500,
      parent_poi_id: parentVal ? parentVal : null,
      physical_effort: backdrop.querySelector("#v-effort").value.trim() || null,
      booking_lead_time: backdrop.querySelector("#v-lead").value.trim() || null,
      indoor_outdoor: backdrop.querySelector("#v-indoor").value || null,
      estimated_duration: backdrop.querySelector("#v-duration").value.trim() || null,
      cost_tier: backdrop.querySelector("#v-cost").value.trim() || null,
      hours_seasonality: cand.hours_seasonality || null,
      best_time_to_visit: backdrop.querySelector("#v-best-time").value.trim() || null,
      website_official: backdrop.querySelector("#v-website").value.trim() || null,
      phone_number: backdrop.querySelector("#v-phone").value.trim() || null,
      primary_image_url: finalSavedImg,
      source_url: originalRequest.page_url,
      source_type: "web",
      raw_selected_text: originalRequest.selected_text,
      iptc_sublocation: cand.iptc_sublocation || null,
      iptc_city: backdrop.querySelector("#v-city").value.trim() || null,
      iptc_province_state: backdrop.querySelector("#v-state").value.trim() || null,
      iptc_country_code: backdrop.querySelector("#v-country").value.trim().toUpperCase() || "US",
      list_ids: Array.from(selectedListIds),
      access_points: [],
    };

    sendExtensionMessage(
      { action: "SAVE_POI", payload: savePayload },
      (saveRes) => {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save to Vistarae";

        if (saveRes && saveRes.success) {
          removeModal();
          showToast(`Successfully saved "${savePayload.name}" to your collection!`);
        } else {
          showToast(saveRes?.error || "Failed to commit POI", true);
        }
      }
    );
  });
}

/**
 * Message listener from background worker.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("%c[Vistarae Content Script] 📨 Received message:", "color: #0d9488;", request);
  if (request.action === "TRIGGER_CAPTURE") {
    console.log("[Vistarae Content Script] Processing TRIGGER_CAPTURE on:", window.location.href);
    initiateCapture(request.text || null);
    sendResponse({ received: true });
  }
});

