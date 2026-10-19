"""Unit tests for Gemini Flash-Lite structured JSON extraction."""

from unittest.mock import MagicMock, patch

import pytest

from app.schemas.extraction import ExtractAndCheckRequest, POIExtractionCandidate
from app.services.extraction import _fallback_heuristic_extraction, extract_candidate_from_text


def test_poi_extraction_candidate_validation():
    valid_data = {
        "name": "Glacier Point Overlook",
        "name_aliases": ["Glacier Point"],
        "poi_type": "photo location",
        "personal_rating": 5,
        "description": "Panoramic view over Yosemite Valley.",
        "category_tags": ["viewpoint", "yosemite"],
        "physical_effort": "paved walk",
        "booking_lead_time": "walk-in ok",
        "indoor_outdoor": "Outdoor",
        "estimated_duration": "1-2 hours",
        "cost_tier": "Free",
        "search_address_query": "Glacier Point, Yosemite, CA",
        "iptc_city": "Yosemite Village",
        "iptc_province_state": "California",
        "iptc_country_code": "US",
    }
    candidate = POIExtractionCandidate.model_validate(valid_data)
    assert candidate.name == "Glacier Point Overlook"
    assert candidate.poi_type == "photo location"
    assert candidate.personal_rating == 5
    assert candidate.indoor_outdoor == "Outdoor"


def test_fallback_heuristic_extraction():
    request = ExtractAndCheckRequest(
        selected_text="Emerald Bay State Park is a state park of California in the United States, centered on Emerald Bay, a Lake Tahoe inlet.",
        page_title="Emerald Bay State Park | Lake Tahoe Travel Guide",
        page_url="https://example.com/emerald-bay",
        og_image_url="https://example.com/emerald-bay.jpg",
    )
    result = _fallback_heuristic_extraction(request)
    assert result.name is not None
    assert len(result.name) > 0
    assert result.poi_type == "site to see"
    assert "Emerald Bay" in result.search_address_query


@pytest.mark.asyncio
async def test_extract_candidate_with_mocked_gemini():
    request = ExtractAndCheckRequest(
        selected_text="Taft Point is a viewpoint in Yosemite National Park west of Glacier Point.",
        page_title="Taft Point Hike",
        page_url="https://example.com/taft-point",
    )

    fake_candidate_json = """{
        "name": "Taft Point",
        "name_aliases": ["Taft Point View"],
        "poi_type": "photo location",
        "personal_rating": 5,
        "description": "Dramatic fissure cliffs and sweeping valley views.",
        "category_tags": ["hiking", "viewpoint"],
        "physical_effort": "moderate hike",
        "booking_lead_time": "walk-in ok",
        "indoor_outdoor": "Outdoor",
        "estimated_duration": "2 hours",
        "cost_tier": "Free",
        "hours_seasonality": "Accessible summer/fall",
        "best_time_to_visit": "Sunset",
        "website_official": "https://www.nps.gov/yose",
        "search_address_query": "Taft Point, Yosemite National Park, California",
        "iptc_sublocation": "Taft Point",
        "iptc_city": "Yosemite Village",
        "iptc_province_state": "California",
        "iptc_country_code": "US",
        "iptc_world_region": "North America"
    }"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = fake_candidate_json
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.config.settings.GEMINI_API_KEY", "test_gemini_key"), \
         patch("google.genai.Client", return_value=mock_client):
        result = await extract_candidate_from_text(request)

        assert result.name == "Taft Point"
        assert result.poi_type == "photo location"
        assert result.personal_rating == 5
        assert result.physical_effort == "moderate hike"
        assert result.iptc_country_code == "US"
        assert "NPS" in result.category_tags


def test_ensure_nps_tag_via_website_and_category():
    # Test 1: NPS detected via nps.gov website
    alcatraz_req = ExtractAndCheckRequest(
        selected_text="",
        page_title="Alcatraz Island - Google Maps",
        page_url="https://www.google.com/maps/place/Alcatraz+Island",
        place_name="Alcatraz Island",
        website="https://www.nps.gov/alca/index.htm",
        category="Historical place",
    )
    res = _fallback_heuristic_extraction(alcatraz_req)
    assert res.name == "Alcatraz Island"
    assert "NPS" in res.category_tags
    assert res.website_official == "https://www.nps.gov/alca/index.htm"

    # Test 2: NPS detected via National Recreation Area category
    golden_gate_req = ExtractAndCheckRequest(
        selected_text="Coastal park with trails and viewpoints.",
        page_title="Marin Headlands",
        page_url="https://example.com/marin",
        category="National recreation area",
    )
    res2 = _fallback_heuristic_extraction(golden_gate_req)
    assert "NPS" in res2.category_tags


def test_infer_category_tags_uss_hornet():
    hornet_req = ExtractAndCheckRequest(
        selected_text="Historic aircraft carrier museum with naval artifacts and Apollo recovery exhibits.",
        page_title="USS Hornet - Sea, Air and Space Museum - Google Maps",
        page_url="https://www.google.com/maps/place/USS+Hornet",
        place_name="USS Hornet - Sea, Air and Space Museum",
        category="Museum",
    )
    res = _fallback_heuristic_extraction(hornet_req)
    assert res.name == "USS Hornet - Sea, Air and Space Museum"
    assert "museum" in res.category_tags
    assert "ship" in res.category_tags
    assert "military" in res.category_tags
    assert "airplane" in res.category_tags
    assert "historic" in res.category_tags
    assert "space" in res.category_tags


def test_parse_atlas_obscura_html():
    from app.services.extraction import parse_atlas_obscura_html

    sample_ao_html = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>Antoine’s Restaurant in New Orleans - Atlas Obscura</title>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": ["Place", "TouristAttraction"],
        "name": "Antoine’s Restaurant",
        "description": "The oldest family-run restaurant in the United States is a living museum of New Orleans dining history.",
        "url": "https://www.atlasobscura.com/places/antoines-restaurant",
        "geo": {
          "@type": "GeoCoordinates",
          "latitude": 29.956737,
          "longitude": -90.066392
        },
        "address": {
          "@type": "PostalAddress",
          "streetAddress": "713 St Louis St",
          "addressLocality": "New Orleans",
          "addressRegion": "Louisiana",
          "postalCode": "70130",
          "addressCountry": "US"
        },
        "image": "https://img.atlasobscura.com/sample.jpg",
        "sameAs": ["https://antoines.com/"]
      }
      </script>
    </head>
    <body>
      <h1>Antoine’s Restaurant</h1>
      <div class="flex flex-wrap gap-4">
        <a href="/categories/restaurants">Restaurants</a>
        <a href="/tags/wine">Wine</a>
        <a href="/tags/history">History</a>
      </div>
      <h2>Know Before You Go</h2>
      <div>Lunch is served Monday to Saturday from 11:30 a.m. to 2:00 p.m., and dinner from 5:30 p.m. to 9:00 p.m. The dress code is business casual. Reservations recommended.</div>
      <div class="place-body">Since 1840, Antoine's Restaurant has been serving French-Creole cuisine in the French Quarter.</div>
    </body>
    </html>
    """
    res = parse_atlas_obscura_html(sample_ao_html, "https://www.atlasobscura.com/places/antoines-restaurant")

    assert res["name"] == "Antoine’s Restaurant"
    assert res["latitude"] == 29.956737
    assert res["longitude"] == -90.066392
    assert res["street_address"] == "713 St Louis St"
    assert res["city"] == "New Orleans"
    assert res["state"] == "Louisiana"
    assert res["country"] == "US"
    assert res["postal_code"] == "70130"
    assert res["website"] == "https://antoines.com/"
    assert res["poi_type"] == "food/drink"
    assert "Restaurants" in res["tags"]
    assert "Wine" in res["tags"]
    assert res["cost_tier"] == "$$$"
    assert res["booking_lead"] == "reservations recommended"
    assert res["environment"] == "Indoor"
    assert res["effort"] == "paved walk"


@pytest.mark.asyncio
async def test_extract_candidate_from_atlas_obscura_url():
    request = ExtractAndCheckRequest(
        selected_text="",
        page_title="Antoine's Restaurant",
        page_url="https://www.atlasobscura.com/places/antoines-restaurant",
        place_name="Antoine's Restaurant",
        latitude=29.956737,
        longitude=-90.066392,
        city="New Orleans",
        state="Louisiana",
        country="US",
        postal_code="70130",
        website="https://antoines.com/",
        category_tags=["Restaurants", "Wine", "History"],
        cost_tier="$$$",
        indoor_outdoor="Indoor",
        physical_effort="paved walk",
        best_time_to_visit="Lunch 11:30am-2:00pm",
        source_type="Atlas Obscura",
    )

    res = await extract_candidate_from_text(request)

    assert res.name == "Antoine's Restaurant"
    assert res.poi_type == "food/drink"
    assert res.iptc_city == "New Orleans"
    assert res.iptc_province_state == "Louisiana"
    assert res.iptc_country_code == "US"
    assert res.website_official == "https://antoines.com/"
    assert "food" in res.category_tags
    assert "historic" in res.category_tags
    assert res.cost_tier == "$$$"
    assert res.indoor_outdoor == "Indoor"
    assert res.physical_effort == "paved walk"


@pytest.mark.asyncio
async def test_extract_candidate_tripadvisor():
    request = ExtractAndCheckRequest(
        selected_text="",
        page_title="Griffin Museum of Science and Industry - TripAdvisor",
        page_url="https://www.tripadvisor.com/Attraction_Review-g35805-d131645-Reviews-Griffin_Museum_of_Science_and_Industry-Chicago_Illinois.html",
        place_name="Griffin Museum of Science and Industry",
        city="Chicago",
        state="Illinois",
        country="United States",
        category="Science Museums",
        category_tags=["museum", "science"],
        estimated_duration="2-3 hours",
        indoor_outdoor="Indoor",
        source_type="TripAdvisor",
    )
    res = await extract_candidate_from_text(request)
    assert res.name == "Griffin Museum of Science and Industry"
    assert res.poi_type == "site to see"
    assert res.iptc_city == "Chicago"

    assert res.iptc_province_state == "Illinois"
    assert "museum" in res.category_tags
    assert "science" in res.category_tags
    assert res.indoor_outdoor == "Indoor"
    assert res.estimated_duration == "2-3 hours"


@pytest.mark.asyncio
async def test_extract_candidate_roadside_america():
    request = ExtractAndCheckRequest(
        selected_text="",
        page_title="Black Chasm Cavern, Volcano, California - RoadsideAmerica.com",
        page_url="https://www.roadsideamerica.com/story/32967",
        place_name="Black Chasm Cavern",
        city="Volcano",
        state="California",
        country="United States",
        category="Cave",
        category_tags=["cave", "natural wonder", "historic"],
        physical_effort="stairs",
        indoor_outdoor="Indoor",
        source_type="RoadsideAmerica",
    )
    res = await extract_candidate_from_text(request)
    assert res.name == "Black Chasm Cavern"
    assert res.iptc_city == "Volcano"
    assert res.iptc_province_state == "California"
    assert "cave" in res.category_tags
    assert res.physical_effort == "stairs"


@pytest.mark.asyncio
async def test_extract_candidate_locationscout():
    request = ExtractAndCheckRequest(
        selected_text="",
        page_title="Machu Picchu - Peru | LocationScout",
        page_url="https://www.locationscout.net/peru/3272-machu-picchu",
        place_name="Machu Picchu",
        country="Peru",
        category="photo location",
        category_tags=["photo location", "historic"],
        indoor_outdoor="Outdoor",
        source_type="LocationScout",
    )
    res = await extract_candidate_from_text(request)
    assert res.name == "Machu Picchu"
    assert res.poi_type == "photo location"
    assert res.iptc_country_code == "Peru" or res.iptc_country_code == "PE"
    assert "photo location" in res.category_tags


@pytest.mark.asyncio
async def test_extract_candidate_shothotspot():
    request = ExtractAndCheckRequest(
        selected_text="",
        page_title="Chichen Itza, Mexico - Best Photo Spots | ShotHotspot",
        page_url="https://www.shothotspot.com/hotspot/mexico/chichen-itza",
        place_name="Chichen Itza",
        latitude=20.6843,
        longitude=-88.5678,
        country="Mexico",
        category="photo location",
        category_tags=["photo location", "historic", "ruins"],
        indoor_outdoor="Outdoor",
        source_type="ShotHotspot",
    )
    res = await extract_candidate_from_text(request)
    assert res.name == "Chichen Itza"
    assert res.poi_type == "photo location"
    assert "photo location" in res.category_tags
    assert "ruins" in res.category_tags


def test_sanitize_official_website():
    from app.services.extraction import sanitize_official_website

    # Blacklisted domains should return None
    assert sanitize_official_website("https://www.google.com/search?q=philadelphia&sca_esv=123") is None
    assert sanitize_official_website("https://maps.google.com/place/Alcatraz") is None
    assert sanitize_official_website("https://www.tripadvisor.com/Attraction_Review-123.html") is None
    assert sanitize_official_website("https://www.roadsideamerica.com/story/32967") is None
    assert sanitize_official_website("https://www.locationscout.net/peru/3272-machu-picchu") is None
    assert sanitize_official_website("https://www.shothotspot.com/hotspot/mexico/chichen-itza") is None
    assert sanitize_official_website("https://www.atlasobscura.com/places/antoines-restaurant") is None
    assert sanitize_official_website("https://en.wikipedia.org/wiki/Philadelphia") is None
    assert sanitize_official_website("https://www.yelp.com/biz/antoines-new-orleans") is None
    assert sanitize_official_website("not-a-valid-url") is None
    assert sanitize_official_website("") is None
    assert sanitize_official_website(None) is None

    # Legitimate official websites should be preserved
    assert sanitize_official_website("https://www.phila.gov") == "https://www.phila.gov"
    assert sanitize_official_website("https://www.nps.gov/yose/index.htm") == "https://www.nps.gov/yose/index.htm"
    assert sanitize_official_website("https://www.easternstate.org") == "https://www.easternstate.org"

    # Google redirect URLs should be properly unwrapped
    redirect_url = "https://www.google.com/url?q=https://www.phila.gov/&sa=U&ved=2ahUKEwi..."
    assert sanitize_official_website(redirect_url) == "https://www.phila.gov/"


def test_page_url_not_defaulted_to_website_official():
    request = ExtractAndCheckRequest(
        selected_text="Philadelphia is the largest city in the Commonwealth of Pennsylvania.",
        page_title="philadelphia - Google Search",
        page_url="https://www.google.com/search?q=philadelphia&sca_esv=123",
        place_name="Philadelphia",
        city="Philadelphia",
        state="Pennsylvania",
    )
    result = _fallback_heuristic_extraction(request)
    # The search page URL must NOT be assigned to website_official
    assert result.website_official is None


def test_sanitize_image_url():
    from app.services.extraction import is_map_or_placeholder_image, sanitize_image_url

    # Static maps and placeholder tiles should be detected and filtered out
    assert is_map_or_placeholder_image("https://maps.google.com/maps/api/staticmap?center=39.9395225,-75.1328185&zoom=14") is True
    assert is_map_or_placeholder_image("https://maps.googleapis.com/maps/api/staticmap?center=39.9395225,-75.1328185") is True
    assert is_map_or_placeholder_image("https://streetviewpixels-pa.googleapis.com/v1/thumbnail?panoid=123") is True
    assert is_map_or_placeholder_image("https://maps.gstatic.com/tactile/omnibox/cleardot.gif") is True
    assert is_map_or_placeholder_image("https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_92x30dp.png") is True
    assert is_map_or_placeholder_image("data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7") is True
    assert is_map_or_placeholder_image("not-a-valid-url") is True
    assert is_map_or_placeholder_image(None) is True

    assert sanitize_image_url("https://maps.google.com/maps/api/staticmap?center=39.9395225,-75.1328185") is None

    # Legitimate place subject photos must be preserved
    real_photo = "https://lh5.googleusercontent.com/p/AF1QipN30X8x9Q_test=w1080-h720-k-no"
    assert is_map_or_placeholder_image(real_photo) is False
    assert sanitize_image_url(real_photo) == real_photo


