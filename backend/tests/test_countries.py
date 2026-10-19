"""Unit tests for country name to ISO 3166-1 alpha-2 code mapping."""

from app.services.countries import map_country_to_code, normalize_country_key, parse_country_input


def test_normalize_country_key():
    assert normalize_country_key("  United States  ") == "united states"
    assert normalize_country_key("People's Republic of China") == "people s republic of china"
    assert normalize_country_key("U.S.A.") == "u s a"
    assert normalize_country_key("Côte d'Ivoire") == "cote d ivoire"
    assert normalize_country_key("São Tomé and Príncipe") == "sao tome and principe"


def test_map_country_to_code_direct_alpha2():
    assert map_country_to_code("US") == "US"
    assert map_country_to_code("us") == "US"
    assert map_country_to_code("cn") == "CN"
    assert map_country_to_code("FR") == "FR"
    assert map_country_to_code("de") == "DE"
    assert map_country_to_code("jp") == "JP"


def test_map_country_to_code_names():
    # User's explicit test case
    assert map_country_to_code("China") == "CN"
    assert map_country_to_code("china") == "CN"
    assert map_country_to_code("CHINA") == "CN"

    # Other common countries
    assert map_country_to_code("United States") == "US"
    assert map_country_to_code("united states of america") == "US"
    assert map_country_to_code("USA") == "US"
    assert map_country_to_code("Japan") == "JP"
    assert map_country_to_code("France") == "FR"
    assert map_country_to_code("Germany") == "DE"
    assert map_country_to_code("United Kingdom") == "GB"
    assert map_country_to_code("UK") == "GB"
    assert map_country_to_code("South Korea") == "KR"
    assert map_country_to_code("Peru") == "PE"
    assert map_country_to_code("Mexico") == "MX"
    assert map_country_to_code("Brazil") == "BR"
    assert map_country_to_code("Brasil") == "BR"
    assert map_country_to_code("Switzerland") == "CH"
    assert map_country_to_code("Canada") == "CA"

    # UNESCO official country names and variants
    assert map_country_to_code("Bolivia (Plurinational State of)") == "BO"
    assert map_country_to_code("Iran (Islamic Republic of)") == "IR"
    assert map_country_to_code("Côte d'Ivoire") == "CI"
    assert map_country_to_code("Ecuador") == "EC"
    assert map_country_to_code("Ukraine") == "UA"
    assert map_country_to_code("North Macedonia") == "MK"
    assert map_country_to_code("Democratic Republic of the Congo") == "CD"
    assert map_country_to_code("Russian Federation") == "RU"


def test_map_country_to_code_invalid_or_empty():
    assert map_country_to_code("") is None
    assert map_country_to_code("   ") is None
    assert map_country_to_code(None) is None
    assert map_country_to_code("NonExistentCountryName12345") is None


def test_parse_country_input_single_and_multi():
    # Single countries
    assert parse_country_input("United States") == ("US", ["US"])
    assert parse_country_input("US") == ("US", ["US"])
    assert parse_country_input("Ecuador") == ("EC", ["EC"])
    assert parse_country_input(None) == (None, [])
    assert parse_country_input("") == (None, [])

    # Multinational UNESCO lists
    prim, codes = parse_country_input("Albania,North Macedonia")
    assert prim == "AL"
    assert codes == ["AL", "MK"]

    prim_qhapaq, codes_qhapaq = parse_country_input(
        "Argentina,Bolivia (Plurinational State of),Chile,Colombia,Ecuador,Peru"
    )
    assert prim_qhapaq == "AR"
    assert codes_qhapaq == ["AR", "BO", "CL", "CO", "EC", "PE"]

    # Transnational Beech forests
    prim_beech, codes_beech = parse_country_input(
        "Albania,Austria,Belgium,Bosnia and Herzegovina,Bulgaria,Croatia,Czechia,France,Germany,Italy,North Macedonia,Poland,Romania,Slovakia,Slovenia,Spain,Switzerland,Ukraine"
    )
    assert prim_beech == "AL"
    assert "UA" in codes_beech
    assert "FR" in codes_beech
    assert "DE" in codes_beech
    assert len(codes_beech) == 18
