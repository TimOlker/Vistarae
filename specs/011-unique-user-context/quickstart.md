<!--
Copyright (c) 2026 Tim Olker

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
-->

# Quickstart & Validation Guide: Phase 11 — Unique User Context

**Feature**: `011-unique-user-context`  
**Date**: 2026-10-27  
**Status**: Ready for Execution

This guide provides step-by-step runnable procedures to validate the implementation of Phase 11 end-to-end across backend services, database migrations, the web application, and the Chrome extension.

---

## 1. Prerequisites & Environment Setup

Verify the local development environment is running Docker containers and services:

```bash
# 1. Start local PostGIS and ElasticMQ
docker compose up -d

# 2. Run database migrations to apply reason_to_visit and user_prompts
alembic upgrade head

# 3. Export OpenAPI specification and regenerate frontend types
python -m scripts.export_openapi
npx openapi-typescript ./openapi.json -o ./frontend/src/types/api.ts

# 4. Start backend gateway and frontend dev server
uvicorn services.local_gateway:app --reload --port 8000
npm --prefix frontend run dev
```

---

## 2. Validation Scenario 1: Travel Style Configuration & Prompt Synthesis

**Goal**: Verify saving a travel style decomposes the narrative into modular prompt directives and caches them.

```bash
# 1. Update traveler travel style narrative
curl -X PUT "http://localhost:8000/api/user/profile/travel-style" \
  -H "Authorization: Bearer $TEST_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "travel_style_description": "I love relaxing vacations taking in local culinary traditions, artisan bakeries, and farmers markets. I want generous time to explore and eat."
  }'

# Expected response: HTTP 200 with travel_style_description and 3 prompt directives:
# - description (food emphasis)
# - reason_to_visit (culinary & sensory focus)
# - time_spent (leisurely pacing)

# 2. Verify prompt retrieval
curl -X GET "http://localhost:8000/api/user/profile/travel-style" \
  -H "Authorization: Bearer $TEST_ACCESS_TOKEN"

# Expected: Returns the 3 active directives.
```

---

## 3. Validation Scenario 2: Web Scraping Extraction with Personalized Context

**Goal**: Verify web scraping generates personalized `description` and `reason_to_visit` tailored to the active profile.

```bash
curl -X POST "http://localhost:8000/api/pois/extract-and-check" \
  -H "Authorization: Bearer $TEST_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source_url": "https://en.wikipedia.org/wiki/Pike_Place_Market",
    "page_title": "Pike Place Market - Wikipedia"
  }'

# Expected response: HTTP 200 with candidate containing:
# - name: "Pike Place Market"
# - description: Focuses on food stalls, fish market, and local farm stands
# - reason_to_visit: Explains experiential food tasting and culinary atmosphere
# - estimated_duration_hours: Adjusted for leisurely exploration (~3.0h)
```

---

## 4. Validation Scenario 3: Full-Text Search on Reason to Visit & Description

**Goal**: Verify keyword queries return POIs whose matching terms reside exclusively in `reason_to_visit`.

```bash
# 1. Create a POI with unique terms in reason_to_visit
curl -X POST "http://localhost:8000/api/pois" \
  -H "Authorization: Bearer $TEST_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "St Andrews Historic Cellar",
    "description": "Historic underground masonry cellar dating to the 14th century.",
    "reason_to_visit": "Exclusive cask-strength single malt tastings in a candlelit vault.",
    "lat": 56.3398,
    "lon": -2.7967
  }'

# 2. Search for the unique term "candlelit vault"
curl -X GET "http://localhost:8000/api/pois?q=candlelit+vault" \
  -H "Authorization: Bearer $TEST_ACCESS_TOKEN"

# Expected response: HTTP 200 with "St Andrews Historic Cellar" in items.
```

---

## 5. Validation Scenario 4: Traveler Login Onboarding Popup & Redirection

**Goal**: Verify unconfigured accounts receive an onboarding modal upon login and redirect to `/profile`.

1. Open Web App in browser (`http://localhost:5173`).
2. Log in with an account having `travel_style_description = NULL`.
3. Assert that `TravelStyleOnboardingModal` displays automatically with the message "Personalize Your Travel Experience!".
4. Click **Set Up Travel Style**.
5. Assert that browser immediately redirects to `http://localhost:5173/profile#travel-style` with the travel style narrative textarea focused.

---

## 6. Automated Test Suite Execution

Run unit, repository, and service tests to enforce Constitution Principle 8 ($\ge 90\%$ test coverage):

```bash
# 1. Run all tests for user context and POI enhancement
pytest tests/unit/services/user/test_prompt_synthesizer.py \
       tests/unit/services/user/test_profile_travel_style.py \
       tests/unit/services/poi/test_scraping_personalized.py \
       tests/unit/repositories/test_user_prompt_repo.py \
       tests/unit/repositories/test_poi_search_reason.py \
       --cov=packages/core/vistarae_core \
       --cov=services/user \
       --cov=services/poi \
       --cov-fail-under=90

# 2. Run frontend component tests including onboarding modal
npm --prefix frontend test
```
