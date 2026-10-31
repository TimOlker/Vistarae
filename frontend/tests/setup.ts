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

import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock window.matchMedia for JSDOM
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock URL.createObjectURL and revokeObjectURL for maplibre-gl in JSDOM
if (typeof window !== "undefined") {
  if (!window.URL.createObjectURL) {
    window.URL.createObjectURL = vi.fn(() => "blob:mock-url");
  }
  if (!window.URL.revokeObjectURL) {
    window.URL.revokeObjectURL = vi.fn();
  }
}

// Global mock for maplibre-gl in JSDOM tests
vi.mock("maplibre-gl", () => {
  const mockMap = {
    on: vi.fn(),
    once: vi.fn(),
    off: vi.fn(),
    loaded: vi.fn(() => true),
    isStyleLoaded: vi.fn(() => true),
    remove: vi.fn(),
    addControl: vi.fn(),
    addSource: vi.fn(),
    addLayer: vi.fn(),
    getSource: vi.fn(),
    getLayer: vi.fn(),
    removeLayer: vi.fn(),
    removeSource: vi.fn(),
    flyTo: vi.fn(),
    resize: vi.fn(),
    jumpTo: vi.fn(),
  };

  const mockMarker = {
    setLngLat: vi.fn().mockReturnThis(),
    addTo: vi.fn().mockReturnThis(),
    remove: vi.fn(),
    getElement: vi.fn(() => document.createElement("div")),
  };

  return {
    default: {
      Map: vi.fn(() => mockMap),
      Marker: vi.fn(() => mockMarker),
      NavigationControl: vi.fn(),
      setWorkerUrl: vi.fn(),
    },
    Map: vi.fn(() => mockMap),
    Marker: vi.fn(() => mockMarker),
    NavigationControl: vi.fn(),
    setWorkerUrl: vi.fn(),
  };
});
