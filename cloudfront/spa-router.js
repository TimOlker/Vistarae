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

/**
 * CloudFront Function: Viewer Request SPA Router
 *
 * Intercepts incoming viewer requests on CloudFront.
 * Rewrites extensionless client-side SPA routes (e.g., /trips, /settings, /planner)
 * internally to /index.html before fetching from private S3 Origin Access Control (OAC),
 * while preserving static fingerprinted assets (/assets/*, .js, .css, images) and /api/* calls.
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // Check if the request is an extensionless path and not an API call
  if (!uri.includes(".") && !uri.startsWith("/api/")) {
    request.uri = "/index.html";
  }

  return request;
}

if (typeof module !== "undefined") {
  module.exports = { handler: handler };
}
