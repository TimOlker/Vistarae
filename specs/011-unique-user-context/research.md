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

# Phase 0 Research: Unique User Context, Personalized LLM Prompts & Reason to Visit Enrichment

**Feature**: `011-unique-user-context`  
**Date**: 2026-10-27  
**Status**: Completed  

---

## 1. Technical Decisions & Research Matrix

### Decision 1: Custom Prompts Persistence & Schema Modeling (`user_prompts`)

- **Context**: Travelers describe their travel style in freeform text on the Web App profile page. An AI decomposes this narrative into specialized prompt directives keyed by target field (`description`, `reason_to_visit`, `time_spent`). These prompt directives must be stored in a dedicated database table, keyed to the user profile and prompt type, and displayed as read-only cards on the user profile.
- **Decision**: Create a dedicated table `user_prompts` in `packages/core/vistarae_core/adapters/db/tables.py` via Alembic migration:
  ```python
  class PromptType(StrEnum):
      DESCRIPTION = "description"
      REASON_TO_VISIT = "reason_to_visit"
      TIME_SPENT = "time_spent"

  class UserPromptTable(Base):
      __tablename__ = "user_prompts"
      id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
      prompt_type: Mapped[str] = mapped_column(String(32), nullable=False)
      prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
      created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
      updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(UTC), nullable=False)

      __table_args__ = (
          UniqueConstraint("user_id", "prompt_type", name="uq_user_prompts_user_type"),
          Index("idx_user_prompts_user_id", "user_id"),
      )
  ```
  Store the raw user narrative in `user_preferences.travel_style_description: Mapped[str | None] = mapped_column(Text, nullable=True)`.
- **Constitutional Alignment**:
  - Principle 3: Child table references `users(id) ON DELETE CASCADE`.
  - Principle 3: No PostgreSQL RLS; tenant isolation strictly enforced in application layer via `WHERE user_id = :current_user_id`.
  - Principle 4: `prompt_type` is typed with Python `StrEnum` backed by PostgreSQL `VARCHAR(32)` column, strictly avoiding native PostgreSQL database `ENUM` types.
- **Alternatives Considered**:
  - _Storing prompts as a single JSONB dictionary on `user_preferences`_: Rejected because the user specification explicitly mandates: "save each set of prompts to a DB table keyed to the users profile + prompt type." A dedicated table allows granular indexing, future expansion of prompt types, and direct repository isolation.
  - _Native PostgreSQL ENUM type for `prompt_type`_: Rejected because Constitution Principle 4 explicitly forbids native PostgreSQL ENUMs to simplify migrations across branches.

---

### Decision 2: In-Memory User Prompts Cache & Invalidation Architecture

- **Context**: To accelerate Chrome Extension captures and high-volume batch CSV imports, user prompt directives must be cached in memory so an API or database query does not need to be executed for every individual POI capture.
- **Decision**: Implement a process-level thread-safe in-memory cache (`UserPromptCache`) in `packages/core/vistarae_core/services/prompt_cache.py`:
  - Storage: In-memory dictionary protected with an `asyncio.Lock` or thread-safe atomic primitives, storing `{user_id: {"prompts": dict[PromptType, str], "cached_at": float}}`.
  - TTL: Default time-to-live of 3,600 seconds (1 hour).
  - Invalidation: Proactive cache eviction triggered immediately upon `PUT /api/user/profile/travel-style`, `DELETE /api/user/profile/travel-style`, or account deletion via `UserPromptCache.invalidate(user_id)`.
  - Fallback: On cache miss or cold-start, fetch from `SqlAlchemyUserPromptRepository`, populate cache, and return.
- **Constitutional Alignment**:
  - Zero-Cost Architecture & AWS Free-Tier Guardrails: Adheres strictly to zero external infrastructure cost. External caching clusters (Redis, ElastiCache, DynamoDB DAX) are avoided. In serverless AWS Lambda, warm container memory reuse caches directives between invocations, with database fallback absorbing cold starts seamlessly.
- **Alternatives Considered**:
  - _Redis / ElastiCache_: Rejected because it introduces external cloud infrastructure cost, violating the Constitution's AWS Free-Tier Guardrails.
  - _Client-only `chrome.storage.local` caching_: Insufficient on its own because Web App manual imports, batch CSV ingestion worker Lambdas, and server-side scraping all require access to the traveler's customized prompt extensions.

---

### Decision 3: AI Prompt Decomposition Engine & Structured Extraction

- **Context**: When the traveler saves their travel style narrative, the system invokes an AI model to extract prompt directives tailored for `description`, `reason_to_visit`, and `time_spent`.
- **Decision**: Implement `UserPromptSynthesizer` in `services/user/services/prompt_synthesizer.py` utilizing Google Gemini Flash-Lite via the Google GenAI SDK:
  - Model: `gemini-2.0-flash-lite` with `thinking_budget = 0` (Constitution Core Rules & Invariants).
  - Structured Output: Enforce Pydantic v2 `StrictBaseModel` schema:
    ```python
    class ExtractedPromptDirectives(StrictBaseModel):
        description: str = Field(..., description="Directive for focusing POI description on traveler preferences")
        reason_to_visit: str = Field(..., description="Directive for highlighting traveler motivation and experiences")
        time_spent: str = Field(..., description="Directive for adjusting pacing and visit duration calculations")
    ```
  - Prompt Engineering & Delimited Isolation: Traveler narrative is wrapped in strict XML delimiter tags (`<traveler_narrative>...</traveler_narrative>`) with system instructions forbidding meta-prompt execution, resisting prompt injection.
  - Directional Messaging: Log outbound call with `MSG   |->` and inbound response with `MSG   |<-` in local development (`STAGE == "local"`).
- **Alternatives Considered**:
  - _Manual regex or rule-based parsing_: Rejected because natural language travel style descriptions ("I love exploring quiet artisan bakeries and pacing trips slowly without checking off lists") require semantic decomposition into distinct actionable directives.

---

### Decision 4: POI Schema Extension & Trigram Search Optimization

- **Context**: Add `reason_to_visit` multiline text field to the POI record, positioned after `description`. Both `description` and `reason_to_visit` must be searchable.
- **Decision**:
  - Alembic Migration: Add `reason_to_visit: Mapped[str | None] = mapped_column(Text, nullable=True)` to `POITable` in `packages/core/vistarae_core/adapters/db/tables.py`.
  - Text Search Query: Update `SqlAlchemyPOIRepository.list_pois` where `text_query` (`q`) matches across:
    ```python
    if text_query:
        pattern = f"%{text_query}%"
        cond = or_(
            POITable.name.ilike(pattern),
            POITable.address.ilike(pattern),
            POITable.city.ilike(pattern),
            POITable.description.ilike(pattern),
            POITable.reason_to_visit.ilike(pattern),
        )
        query = query.where(cond)
        count_query = count_query.where(cond)
    ```
  - Indexing: Update PostgreSQL GiST / GIN trigram indexes (`gin_trgm_ops`) on `pois` to include `description` and `reason_to_visit`, maintaining high performance during freeform keyword searches.
- **Alternatives Considered**:
  - _Elasticsearch / OpenSearch cluster_: Rejected due to AWS infrastructure cost and complexity. PostgreSQL's built-in `pg_trgm` and `ILIKE` handle thousands of POIs per tenant with sub-50ms query latency.

---

### Decision 5: Personalized Multi-Source POI Synthesis & Grounding Policy

- **Context**: During web scraping (Extension), manual POI creation (Web App), and batch CSV ingestion, the orchestrator synthesizes `description` and `reason_to_visit` from primary and secondary scraped website text using base prompts extended by the traveler's custom directives.
- **Decision**: Update `ScrapingOrchestrator` in `services/poi/scraping/orchestrator.py`:
  1. Base `description` prompt: "Summarize what this location is objectively (history, structure, core features)." Extended by `user_prompts['description']` (e.g., "Emphasize local food culture or architectural details if present").
  2. Base `reason_to_visit` prompt: "Explain compelling reasons why a tourist would be interested in visiting this location." Extended by `user_prompts['reason_to_visit']` (e.g., "Highlight authentic food tastings, bakeries, or relaxing atmospheres").
  3. Base `time_spent` heuristic: Base category duration adjusted according to `user_prompts['time_spent']` (e.g. extending duration by 1.5x for relaxed pacing).
  4. Non-overlapping POI Policy (User Clarification Q2): If the scraped destination shares no thematic overlap with the traveler's preferences (e.g. beach destination for a castle-focused traveler), the synthesizer generates authentic objective descriptions and reasons to visit without forcing irrelevant references or hallucinating non-existent features.
  5. Retroactive Scope (User Clarification Q1): Prompt directives apply strictly to new captures and explicit on-demand re-enrichment requests. Existing saved POIs remain untouched to preserve user edits and token quotas.
- **Alternatives Considered**:
  - _Generating `reason_to_visit` in a separate LLM call_: Rejected to minimize latency and token consumption. Combining `description`, `reason_to_visit`, and duration notes into a single structured Gemini call cuts token usage and latency in half.

---

### Decision 6: UI Parity, Layout & Search Experience

- **Context**: The `Reason to Visit` field must be visible on the POI edit field on the web app as well as in the extension web scraping logic, placed immediately after `Description`.
- **Decision**:
  - Web App Profile (`ProfilePage.tsx`): Add "Travel Style & Preferences" card with multiline textarea, Save button with loading spinner, and read-only preview cards displaying active prompt directives for `description`, `reason_to_visit`, and `time_spent`.
  - Web App POI Edit Drawer (`POIEditDrawer.tsx`) & Manual Add Modal (`ManualAddPOIModal.tsx`): Insert `Reason to Visit` multiline textarea directly beneath `Description`, with identical typography, placeholder guidance, and character counters.
  - Web App POI Detail Drawer (`POIDetailDrawer.tsx`): Render "Why Visit" section card immediately below the description card.
  - Web App POI Table (`POITable.tsx`): Add optional column toggle for `Reason to Visit` with text truncation and tooltip on hover. Update client-side quick filter to search across both `description` and `reason_to_visit`.
  - Chrome Extension Review Overlay (`content_script.js`, `overlay.css`): Update Shadow DOM capture form to place `Reason to Visit` textarea directly below `Description` textarea.
- **Alternatives Considered**:
  - _Tabs for Description vs. Reason to Visit_: Rejected because the user explicitly specified: "the 'Reason to Visit' field should be displayed after the 'Description' field" for natural vertical scannability.

---

### Decision 7: Traveler Onboarding Popup & Login Redirection Architecture

- **Context**: When a user logs in and their travel style in their profile is not populated (either a new user or an existing un-migrated account), display a popup message indicating that the user should fill this out and redirect the user to the profile page so they can fill it out.
- **Decision**:
  - Component: Implement `TravelStyleOnboardingModal` in `frontend/src/components/profile/TravelStyleOnboardingModal.tsx`.
  - Trigger Logic: On successful login or session initialization in `frontend/src/context/AuthContext.tsx` or `frontend/src/pages/HomePage.tsx`, evaluate `user.travel_style_description` (or `userPreferences.travel_style_description`).
  - Presentation: If null or empty and not previously dismissed during the current session, render an informative modal highlighting the personalization benefits:
    "Personalize Your Travel Experience! Vistarae customizes POI descriptions, reasons to visit, and visit times based on your travel goals. Please describe what you look for in travel."
  - Action & Redirection: Primary button "Set Up Travel Style" navigates to `/profile#travel-style` and focuses the travel style narrative textarea. Secondary action "Remind Me Later" dismisses the modal for the current session.
- **Alternatives Considered**:
  - _Forced modal blocking all navigation_: Rejected because it degrades user experience if a traveler urgently needs to look up a saved POI or itinerary during travel. An informative modal with one-click redirection and "Remind Me Later" achieves high adoption while respecting user autonomy.
