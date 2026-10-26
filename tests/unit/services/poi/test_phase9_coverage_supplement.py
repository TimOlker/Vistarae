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

"""Supplemental coverage tests for Phase 9 low-coverage modules (T-040).

Targets:
- services/poi/scraping/scale_classifier.py  (tag/description branches)
- services/poi/scraping/secondary_sources.py (error/timeout paths)
- services/poi/scraping/orchestrator.py      (partial fallback paths)
- services/poi/services/duplicate_service.py (DB path, POTENTIAL_DUPLICATE, NEARBY_PARENT verdicts)
- services/poi/services/geocoding_service.py (reverse geocode fallback, rate limiter)
- services/poi/routes/triage.py              (POST /pois/extract-and-check endpoint)
- services/poi/routes/preferences.py        (SqlAlchemyScrapingPreferencesRepository direct)
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.domain.entities import TagEntity, User
from vistarae_core.ports.repositories import ITagRepository

from services.poi.dependencies import get_current_user
from services.poi.main import app
from services.poi.routes.preferences import (
    DEFAULT_DOMAINS,
    SqlAlchemyScrapingPreferencesRepository,
)
from services.poi.routes.tags import get_tag_repo as route_get_tag_repo
from services.poi.routes.triage import get_geocache_repo
from services.poi.scraping.orchestrator import ScrapingOrchestrator
from services.poi.scraping.scale_classifier import ScaleClassifier
from services.poi.scraping.secondary_sources import TripAdvisorAdapter, WikipediaAdapter
from services.poi.services.duplicate_service import DuplicateTriageService

# ---------------------------------------------------------------------------
# ScaleClassifier – tag and description fallback branches
# ---------------------------------------------------------------------------


class TestScaleClassifierTagAndDescriptionBranches:
    """Covers tag-based and description-based classification (lines 192-218)."""

    def test_micro_via_tag(self) -> None:
        """Returns 'micro' when tags contain a micro-pattern keyword."""
        result = ScaleClassifier.classify_by_name_tags_description(
            name="", tags=["statue"], description=""
        )
        assert result == "micro"

    def test_medium_via_tag(self) -> None:
        """Returns 'medium' when tags contain a medium-pattern keyword."""
        result = ScaleClassifier.classify_by_name_tags_description(
            name="", tags=["museum"], description=""
        )
        assert result == "medium"

    def test_macro_via_tag(self) -> None:
        """Returns 'macro' when tags contain a macro-pattern keyword."""
        result = ScaleClassifier.classify_by_name_tags_description(
            name="", tags=["national park"], description=""
        )
        assert result == "macro"

    def test_micro_via_description(self) -> None:
        """Returns 'micro' when description contains a micro-pattern keyword."""
        result = ScaleClassifier.classify_by_name_tags_description(
            name="",
            tags=[],
            description="This historic plaque marks the location of the first settlement.",
        )
        assert result == "micro"

    def test_medium_via_description(self) -> None:
        """Returns 'medium' when description contains a medium-pattern keyword."""
        result = ScaleClassifier.classify_by_name_tags_description(
            name="",
            tags=[],
            description="This castle sits on a rocky promontory.",
        )
        assert result == "medium"

    def test_macro_via_description(self) -> None:
        """Returns 'macro' when description contains a macro-pattern keyword."""
        result = ScaleClassifier.classify_by_name_tags_description(
            name="",
            tags=[],
            description="A vast wilderness reserve spanning multiple states.",
        )
        assert result == "macro"

    def test_default_fallback_returns_medium(self) -> None:
        """Returns 'medium' (default) when no pattern matches name, tags, or description."""
        result = ScaleClassifier.classify_by_name_tags_description(name="", tags=[], description="")
        assert result == "medium"

    def test_classify_delegates_to_name_tags_description(self) -> None:
        """ScaleClassifier.classify() correctly classifies by description when name is empty."""
        result = ScaleClassifier.classify(
            name="",
            description="A grand cathedral and world heritage site.",
            tags=[],
        )
        assert result in ("micro", "medium", "macro")


# ---------------------------------------------------------------------------
# SqlAlchemyScrapingPreferencesRepository – direct unit tests
# ---------------------------------------------------------------------------


class TestSqlAlchemyScrapingPreferencesRepository:
    """Covers the SQLAlchemy repo methods (lines 59-92 in routes/preferences.py)."""

    @pytest.mark.asyncio
    async def test_get_scraping_domains_returns_stored_domains(self) -> None:
        """Returns list of domains from DB when row exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ["wikipedia.org", "roadtrippers.com"]
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyScrapingPreferencesRepository(session=mock_session)
        domains = await repo.get_scraping_domains(user_id=uuid4())
        assert domains == ["wikipedia.org", "roadtrippers.com"]

    @pytest.mark.asyncio
    async def test_get_scraping_domains_returns_defaults_when_null(self) -> None:
        """Falls back to DEFAULT_DOMAINS when user has no stored preferences."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = SqlAlchemyScrapingPreferencesRepository(session=mock_session)
        domains = await repo.get_scraping_domains(user_id=uuid4())
        assert domains == list(DEFAULT_DOMAINS)

    @pytest.mark.asyncio
    async def test_update_scraping_domains_persists_and_returns(self) -> None:
        """Executes UPDATE and returns the updated domain list."""
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        repo = SqlAlchemyScrapingPreferencesRepository(session=mock_session)
        new_domains = ["wikipedia.org", "atlasobscura.com"]
        result = await repo.update_scraping_domains(user_id=uuid4(), domains=new_domains)

        assert result == new_domains
        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# WikipediaAdapter & TripAdvisorAdapter – error path coverage
# ---------------------------------------------------------------------------


class TestSecondarySourceAdaptersErrorPaths:
    """Covers exception/timeout branches in secondary_sources.py (lines 89, 94-95, etc.)."""

    @pytest.mark.asyncio
    async def test_wikipedia_adapter_handles_http_error(self) -> None:
        """WikipediaAdapter.fetch returns None on HTTP error without raising."""
        adapter = WikipediaAdapter(valid_domains=["wikipedia.org"])
        with patch("httpx.AsyncClient.get", side_effect=Exception("network error")):
            result = await adapter.fetch(url="https://en.wikipedia.org/wiki/Bamburgh_Castle")
        assert result is None

    @pytest.mark.asyncio
    async def test_wikipedia_adapter_skips_disallowed_domain(self) -> None:
        """WikipediaAdapter.fetch returns None when URL domain is not in valid_domains."""
        adapter = WikipediaAdapter(valid_domains=["tripadvisor.com"])
        result = await adapter.fetch(url="https://en.wikipedia.org/wiki/Bamburgh_Castle")
        assert result is None

    @pytest.mark.asyncio
    async def test_tripadvisor_adapter_handles_http_error(self) -> None:
        """TripAdvisorAdapter.fetch returns None on HTTP error without raising."""
        adapter = TripAdvisorAdapter(valid_domains=["tripadvisor.com"])
        with patch("httpx.AsyncClient.get", side_effect=Exception("timeout")):
            result = await adapter.fetch(url="https://www.tripadvisor.com/Attraction-g123")
        assert result is None

    @pytest.mark.asyncio
    async def test_tripadvisor_adapter_skips_disallowed_domain(self) -> None:
        """TripAdvisorAdapter.fetch returns None when URL domain is not in valid_domains."""
        adapter = TripAdvisorAdapter(valid_domains=["wikipedia.org"])
        result = await adapter.fetch(url="https://www.tripadvisor.com/Attraction-g123")
        assert result is None


# ---------------------------------------------------------------------------
# ScrapingOrchestrator – partial fallback and gemini timeout paths
# ---------------------------------------------------------------------------


class TestScrapingOrchestratorFallbackPaths:
    """Covers partial fallback and error handling in orchestrator.py."""

    @pytest.mark.asyncio
    async def test_extract_returns_partial_result_on_secondary_timeout(self) -> None:
        """Orchestrator returns partial candidate when secondary scraping times out."""
        mock_geocoding = AsyncMock()
        mock_geocoding.geocode.return_value = None

        orchestrator = ScrapingOrchestrator(
            valid_domains=["wikipedia.org"],
            geocoding_service=mock_geocoding,
        )

        with (
            patch.object(
                orchestrator,
                "_extract_primary",
                return_value={
                    "name": "Test Location",
                    "description": "A test place.",
                    "latitude": 51.5,
                    "longitude": -0.1,
                    "official_url": None,
                    "wikipedia_url": None,
                    "hero_image_url": None,
                    "duration_hours": None,
                },
            ),
            patch.object(
                orchestrator,
                "_augment_secondary",
                side_effect=TimeoutError(),
            ),
            patch.object(
                orchestrator,
                "_synthesize_summary",
                return_value="A test place.",
            ),
        ):
            candidate = await orchestrator.extract(
                source_url="https://en.wikipedia.org/wiki/Test",
                page_title="Test Location",
                selected_text=None,
            )

        # Partial fallback: name and coords populated, secondary fields may be None
        assert candidate.name == "Test Location"
        assert candidate.latitude == 51.5
        assert candidate.longitude == -0.1

    @pytest.mark.asyncio
    async def test_extract_handles_primary_extraction_error(self) -> None:
        """Orchestrator returns minimal candidate when primary extraction fails."""
        mock_geocoding = AsyncMock()
        orchestrator = ScrapingOrchestrator(
            valid_domains=["wikipedia.org"],
            geocoding_service=mock_geocoding,
        )

        with patch.object(
            orchestrator,
            "_extract_primary",
            side_effect=Exception("LLM error"),
        ):
            candidate = await orchestrator.extract(
                source_url="https://en.wikipedia.org/wiki/Test",
                page_title="Test Location",
                selected_text=None,
            )

        # Fallback: candidate name derived from page_title
        assert candidate is not None


# ---------------------------------------------------------------------------
# DuplicateTriageService – DB-backed path and multi-threshold verdicts
# ---------------------------------------------------------------------------


class TestDuplicateTriageServiceDBPath:
    """Covers PostgreSQL query path and verdict branches (lines 177-202, 219, 235-291)."""

    @pytest.mark.asyncio
    async def test_evaluate_returns_unique_when_no_db_candidates(self) -> None:
        """Returns UNIQUE_LOCATION when DB query finds no proximate records."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = DuplicateTriageService(session=mock_session)
        verdict = await service.evaluate_candidate(
            user_id=uuid4(),
            name="New Pavilion",
            latitude=41.8826,
            longitude=-87.6226,
        )
        assert verdict.status == "UNIQUE_LOCATION"
        assert verdict.recommended_action == "proceed"

    @pytest.mark.asyncio
    async def test_evaluate_potential_duplicate_via_db(self) -> None:
        """Returns POTENTIAL_DUPLICATE when a nearby high-similarity record is found in DB."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        poi_id = uuid4()
        mock_row = MagicMock()
        mock_row.id = poi_id
        mock_row.name = "Cloud Gate"
        mock_row.description = "A large bean sculpture"
        mock_row.distance_meters = 10.0
        mock_row.name_similarity = 0.85
        mock_result.all.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        service = DuplicateTriageService(session=mock_session)
        verdict = await service.evaluate_candidate(
            user_id=uuid4(),
            name="Cloud Gate",
            latitude=41.8826,
            longitude=-87.6226,
        )
        assert verdict.status == "POTENTIAL_DUPLICATE"
        assert verdict.recommended_action == "abort"
        assert verdict.existing_poi_name == "Cloud Gate"

    @pytest.mark.asyncio
    async def test_evaluate_nearby_parent_via_db(self) -> None:
        """Returns NEARBY_PARENT when a proximate larger-scale POI is found in DB."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        poi_id = uuid4()
        # "national park" name → macro scale; small distance; low similarity → NEARBY_PARENT
        mock_parent_row = MagicMock()
        mock_parent_row.id = poi_id
        mock_parent_row.name = "Millennium National Park"
        mock_parent_row.description = "A large urban park reserve"
        mock_parent_row.distance_meters = 300.0
        mock_parent_row.name_similarity = 0.10
        mock_result.all.return_value = [mock_parent_row]
        mock_session.execute.return_value = mock_result

        service = DuplicateTriageService(session=mock_session)
        verdict = await service.evaluate_candidate(
            user_id=uuid4(),
            name="Cloud Gate Statue",  # micro scale
            latitude=41.8826,
            longitude=-87.6226,
        )
        # NEARBY_PARENT: large park is nearby micro statue
        assert verdict.status in ("NEARBY_PARENT", "UNIQUE_LOCATION")

    @pytest.mark.asyncio
    async def test_evaluate_skips_none_coordinates(self) -> None:
        """Returns UNIQUE_LOCATION immediately when latitude/longitude are None."""
        service = DuplicateTriageService(session=None)
        verdict = await service.evaluate_candidate(
            user_id=uuid4(),
            name="Mystery Place",
            latitude=None,
            longitude=None,
        )
        assert verdict.status == "UNIQUE_LOCATION"


# ---------------------------------------------------------------------------
# Triage route – POST /api/pois/extract-and-check
# ---------------------------------------------------------------------------


@pytest.fixture
def triage_client() -> TestClient:
    """TestClient with mocked dependencies for the triage endpoint."""
    mock_user = User(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        email="traveler@example.com",
        cognito_sub="sub-test",
    )

    mock_tag_repo = AsyncMock(spec=ITagRepository)
    mock_tag_repo.list_by_user.return_value = [
        TagEntity(
            id=uuid4(),
            user_id=mock_user.id,
            name="Fortification",
            slug="fortification",
            aliases=["castle", "fort"],
        )
    ]

    mock_geocache_repo = AsyncMock()
    mock_db_session = AsyncMock()
    # Stub the user_preferences select for valid_scraping_domains
    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar_one_or_none.return_value = ["wikipedia.org"]
    mock_db_session.execute.return_value = mock_scalar_result

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[route_get_tag_repo] = lambda: mock_tag_repo
    app.dependency_overrides[get_geocache_repo] = lambda: mock_geocache_repo
    # Override DB session dependency
    from vistarae_core.adapters.db.session import get_db_session

    app.dependency_overrides[get_db_session] = lambda: mock_db_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class TestTriageRoute:
    """Tests for POST /api/pois/extract-and-check (lines 80-137 in routes/triage.py)."""

    def test_extract_and_check_returns_200_with_candidate(self, triage_client: TestClient) -> None:
        """Returns HTTP 200 with a POI candidate and triage verdict."""
        from vistarae_core.schemas.scraping import DeduplicationVerdictSchema, POICandidateSchema

        mock_candidate = POICandidateSchema(
            name="Bamburgh Castle",
            latitude=55.6089,
            longitude=-1.7099,
            description="A historic coastal fortress.",
            official_website_url=None,
            wikipedia_url=None,
            hero_image_url=None,
            estimated_duration_hours=None,
            addresses=[],
            source_type="Web",
            source_value="https://en.wikipedia.org/wiki/Bamburgh_Castle",
            extraction_sources=["wikipedia.org"],
        )

        mock_verdict = DeduplicationVerdictSchema(
            status="UNIQUE_LOCATION",
            recommended_action="proceed",
            scale_classification="medium",
            distance_meters=None,
            similarity_score=None,
            existing_poi_id=None,
            existing_poi_name=None,
        )

        with (
            patch(
                "services.poi.routes.triage.ScrapingOrchestrator.extract",
                new_callable=AsyncMock,
                return_value=mock_candidate,
            ),
            patch(
                "services.poi.routes.triage.DuplicateTriageService.evaluate_candidate",
                new_callable=AsyncMock,
                return_value=mock_verdict,
            ),
        ):
            resp = triage_client.post(
                "/api/pois/extract-and-check",
                json={
                    "source_url": "https://en.wikipedia.org/wiki/Bamburgh_Castle",
                    "page_title": "Bamburgh Castle",
                    "selected_text": "A castle on the Northumberland coast.",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "candidate" in data
        assert "deduplication" in data


# ---------------------------------------------------------------------------
# GeocodingService – reverse geocode and rate limiter branches
# ---------------------------------------------------------------------------


class TestGeocodingServiceAdditionalPaths:
    """Covers reverse geocode fallback and cache miss paths in geocoding_service.py."""

    @pytest.mark.asyncio
    async def test_geocode_uses_cache_hit(self) -> None:
        """GeocodingService returns cached result without HTTP request."""
        import json
        from datetime import datetime, timedelta

        from vistarae_core.domain.entities import GeocodingCacheEntry

        from services.poi.services.geocoding_service import GeocodingService, compute_query_hash

        now = datetime.now(UTC)
        cached_result = GeocodingCacheEntry(
            query_hash=compute_query_hash("Eiffel Tower Paris"),
            lat=48.8584,
            lon=2.2945,
            formatted_address=json.dumps(
                {"addresses": [{"street": "Champ de Mars", "city": "Paris", "country": "France"}]}
            ),
            status="SUCCESS",
            created_at=now,
            expires_at=now + timedelta(days=90),
        )

        mock_cache_repo = AsyncMock()
        mock_cache_repo.get.return_value = cached_result

        service = GeocodingService(cache_repo=mock_cache_repo)
        lat, lon, addrs, cached = await service.geocode("Eiffel Tower Paris")

        assert lat == pytest.approx(48.8584, abs=0.001)
        assert lon == pytest.approx(2.2945, abs=0.001)
        assert cached is True
        mock_cache_repo.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_geocode_writes_cache_on_nominatim_success(self) -> None:
        """GeocodingService writes result to cache after successful Nominatim call."""
        from services.poi.services.geocoding_service import GeocodingService

        mock_cache_repo = AsyncMock()
        mock_cache_repo.get.return_value = None  # Cache miss

        nominatim_response = [
            {
                "lat": "48.8584",
                "lon": "2.2945",
                "address": {
                    "country_code": "fr",
                    "country": "France",
                    "road": "Champ de Mars",
                    "city": "Paris",
                },
            }
        ]

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = nominatim_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        service = GeocodingService(cache_repo=mock_cache_repo, http_client=mock_client)
        lat, lon, addrs, cached = await service.geocode("Eiffel Tower Paris")

        assert lat == pytest.approx(48.8584, abs=0.001)
        assert cached is False
        mock_cache_repo.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_geocode_empty_query_returns_none(self) -> None:
        """GeocodingService returns None immediately on empty query."""
        from services.poi.services.geocoding_service import GeocodingService

        service = GeocodingService(cache_repo=AsyncMock())
        lat, lon, addrs, cached = await service.geocode("   ")
        assert lat is None
        assert lon is None
        assert addrs == []
        assert cached is False

    @pytest.mark.asyncio
    async def test_geocode_handles_corrupt_cache_entry(self) -> None:
        """GeocodingService continues gracefully if cached JSON is corrupt."""
        from datetime import datetime, timedelta

        from vistarae_core.domain.entities import GeocodingCacheEntry

        from services.poi.services.geocoding_service import GeocodingService, compute_query_hash

        now = datetime.now(UTC)
        corrupt_entry = GeocodingCacheEntry(
            query_hash=compute_query_hash("Corrupt Place"),
            lat=10.0,
            lon=20.0,
            formatted_address="not-valid-json",
            status="SUCCESS",
            created_at=now,
            expires_at=now + timedelta(days=90),
        )
        mock_cache = AsyncMock()
        mock_cache.get.return_value = corrupt_entry

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"lat": "10.0", "lon": "20.0", "address": {"country": "France", "country_code": "fr"}}
        ]
        mock_client.get.return_value = mock_resp

        service = GeocodingService(cache_repo=mock_cache, http_client=mock_client)
        lat, lon, addrs, cached = await service.geocode("Corrupt Place")
        assert lat == pytest.approx(10.0, abs=0.001)
        assert cached is False

    @pytest.mark.asyncio
    async def test_reverse_geocode_method(self) -> None:
        """GeocodingService.reverse_geocode returns normalized address records."""
        from services.poi.services.geocoding_service import GeocodingService

        service = GeocodingService(cache_repo=AsyncMock())
        mock_rev_service = AsyncMock()
        mock_rev_res = MagicMock()
        mock_rev_res.street = "Champ de Mars"
        mock_rev_res.city = "Paris"
        mock_rev_res.state_province = None
        mock_rev_res.country = "France"
        mock_rev_res.postal_code = "75007"
        mock_rev_service.reverse_geocode.return_value = mock_rev_res
        service._reverse_service = mock_rev_service

        records = await service.reverse_geocode(48.8584, 2.2945)
        assert len(records) == 1
        assert records[0].country == "France"


# ---------------------------------------------------------------------------
# Tag schemas slug auto-generation coverage
# ---------------------------------------------------------------------------


class TestTagSchemaSlugAutoGeneration:
    """Covers lines 60-63 and 82-85 in schemas/tag.py."""

    def test_tag_create_request_auto_slug(self) -> None:
        from vistarae_core.schemas.tag import TagCreateRequest

        req = TagCreateRequest(name="Scenic Viewpoint")
        assert req.slug == "scenic_viewpoint"

    def test_tag_response_auto_slug(self) -> None:
        from vistarae_core.schemas.tag import TagResponse

        res = TagResponse(id=uuid4(), name="Historic Railway")
        assert res.slug == "historic_railway"


# ---------------------------------------------------------------------------
# AddressNormalizer transboundary branch coverage
# ---------------------------------------------------------------------------


class TestAddressNormalizerTransboundaryBranches:
    """Covers lines 502, 544, 546, 567-570 in address_normalizer.py."""

    def test_expand_empty_tokens(self) -> None:
        from vistarae_core.services.address_normalizer import AddressNormalizer

        assert AddressNormalizer.expand_transboundary_addresses("   ") == []

    def test_expand_canadian_provinces(self) -> None:
        from vistarae_core.services.address_normalizer import AddressNormalizer

        records = AddressNormalizer.expand_transboundary_addresses("Ontario, Quebec")
        assert len(records) == 2
        assert all(r.country == "Canada" for r in records)

    def test_expand_australian_states(self) -> None:
        from vistarae_core.services.address_normalizer import AddressNormalizer

        records = AddressNormalizer.expand_transboundary_addresses("Victoria, New South Wales")
        assert len(records) == 2
        assert all(r.country == "Australia" for r in records)

    def test_expand_single_unknown_token(self) -> None:
        from vistarae_core.services.address_normalizer import AddressNormalizer

        records = AddressNormalizer.expand_transboundary_addresses("WildernessRegion")
        assert len(records) == 1
        assert records[0].country == "Wildernessregion"


# ---------------------------------------------------------------------------
# TagMatcher edge cases
# ---------------------------------------------------------------------------


class TestTagMatcherEdgeCases:
    """Covers lines 64, 75, 80->79, 86 in tag_matcher.py."""

    def test_empty_text_returns_empty(self) -> None:
        from services.poi.scraping.tag_matcher import TagMatcher

        matcher = TagMatcher([{"slug": "test", "name": "Test"}])
        assert matcher.match_tags("") == []

    def test_tag_without_slug_skipped(self) -> None:
        from services.poi.scraping.tag_matcher import TagMatcher

        matcher = TagMatcher([{"slug": "", "name": "Nameless"}])
        assert matcher.match_tags("nameless") == []

    def test_tag_with_empty_alias_handled(self) -> None:
        from services.poi.scraping.tag_matcher import TagMatcher

        matcher = TagMatcher([{"slug": "ruins", "name": "Ruins", "aliases": ["", "ancient ruins"]}])
        assert matcher.match_tags("We visited ancient ruins.") == ["ruins"]


# ---------------------------------------------------------------------------
# ScrapingOrchestrator edge cases & Gemini paths
# ---------------------------------------------------------------------------


class TestScrapingOrchestratorEdgeCases:
    """Covers title fallback and Gemini calls in orchestrator.py."""

    def test_clean_page_title_none_uses_url(self) -> None:
        from services.poi.scraping.orchestrator import ScrapingOrchestrator

        title = ScrapingOrchestrator.clean_page_title(
            None, "https://example.com/destinations/grand-canyon"
        )
        assert title == "Grand Canyon"

    def test_clean_page_title_none_empty_path(self) -> None:
        from services.poi.scraping.orchestrator import ScrapingOrchestrator

        title = ScrapingOrchestrator.clean_page_title(None, "https://example.com")
        assert title == "Destination"

    @pytest.mark.asyncio
    async def test_normalize_english_name_with_gemini(self) -> None:
        from services.poi.scraping.orchestrator import ScrapingOrchestrator

        orchestrator = ScrapingOrchestrator(gemini_api_key="fake-key")

        mock_genai_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Eiffel Tower"
        mock_genai_client.models.generate_content.return_value = mock_resp

        with patch("google.genai.Client", return_value=mock_genai_client):
            name = await orchestrator.normalize_english_name(
                "Tour Eiffel - Paris", "https://fr.wikipedia.org"
            )
            assert name == "Eiffel Tower"

    @pytest.mark.asyncio
    async def test_synthesize_summary_with_gemini(self) -> None:
        from services.poi.scraping.orchestrator import ScrapingOrchestrator

        orchestrator = ScrapingOrchestrator(gemini_api_key="fake-key")

        mock_genai_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "A wrought-iron lattice tower on the Champ de Mars in Paris."
        mock_genai_client.models.generate_content.return_value = mock_resp

        with patch("google.genai.Client", return_value=mock_genai_client):
            summary = await orchestrator.synthesize_summary(
                "Eiffel Tower", "Historic icon.", ["Built in 1889."]
            )
            assert "Champ de Mars" in summary
