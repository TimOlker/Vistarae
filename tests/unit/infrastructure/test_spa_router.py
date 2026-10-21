# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for CloudFront Function viewer request SPA router (T032)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

SPA_ROUTER_PATH = Path(__file__).resolve().parents[3] / "cloudfront" / "spa-router.js"


def _run_spa_router(uri: str) -> str:
    """Executes spa-router.js via Node.js runtime and returns transformed request uri."""
    js_script = f"""
    const router = require({json.dumps(str(SPA_ROUTER_PATH))});
    const event = {{
        request: {{
            uri: {json.dumps(uri)}
        }}
    }};
    const result = router.handler(event);
    console.log(JSON.stringify(result.uri));
    """
    proc = subprocess.run(
        ["node", "-e", js_script],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip())


class TestSpaRouter:
    """Verifies that spa-router.js rewrites extensionless routes and preserves assets/APIs."""

    @pytest.mark.parametrize(
        "client_route",
        [
            "/",
            "/trips",
            "/planner",
            "/settings",
            "/explore/pacific-northwest",
            "/itinerary/123-abc/edit",
        ],
    )
    def test_extensionless_spa_routes_rewrite_to_index(self, client_route: str) -> None:
        """Client-side extensionless routes must be rewritten to /index.html for SPA routing."""
        rewritten = _run_spa_router(client_route)
        assert rewritten == "/index.html"

    @pytest.mark.parametrize(
        "asset_route",
        [
            "/assets/index-Bf3902.js",
            "/assets/main-29fk3.css",
            "/vite.svg",
            "/favicon.ico",
            "/icons/icon-192.png",
            "/manifest.webmanifest",
        ],
    )
    def test_static_assets_with_extensions_preserved(self, asset_route: str) -> None:
        """Static fingerprinted assets with extensions must NOT be rewritten."""
        rewritten = _run_spa_router(asset_route)
        assert rewritten == asset_route

    @pytest.mark.parametrize(
        "api_route",
        [
            "/api/health",
            "/api/pois",
            "/api/itineraries",
            "/api/itineraries/generate",
            "/api/users/me",
        ],
    )
    def test_api_routes_preserved(self, api_route: str) -> None:
        """Backend /api/* calls must NOT be rewritten."""
        rewritten = _run_spa_router(api_route)
        assert rewritten == api_route
