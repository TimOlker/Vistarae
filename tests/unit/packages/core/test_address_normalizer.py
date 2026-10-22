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

"""Unit tests for AddressNormalizer (REQ-EDIT-003, REQ-EDIT-004)."""

from vistarae_core.domain.value_objects import AddressRecord
from vistarae_core.services.address_normalizer import AddressNormalizer


def test_normalize_country_iso_and_aliases():
    """Verifies country code and endonym resolution to official English names."""
    assert AddressNormalizer.normalize_country("DE") == "Germany"
    assert AddressNormalizer.normalize_country("deutschland") == "Germany"
    assert AddressNormalizer.normalize_country("USA") == "United States"
    assert AddressNormalizer.normalize_country("united states of america") == "United States"
    assert AddressNormalizer.normalize_country("UK") == "United Kingdom"
    assert AddressNormalizer.normalize_country("España") == "Spain"
    assert AddressNormalizer.normalize_country("Schweiz") == "Switzerland"
    assert AddressNormalizer.normalize_country("jp") == "Japan"
    assert AddressNormalizer.normalize_country("AU") == "Australia"
    assert AddressNormalizer.normalize_country("UNKNOWN_LAND") == "Unknown_land"
    assert AddressNormalizer.normalize_country("") == ""


def test_normalize_state_province():
    """Verifies state/province normalization across US, Canada, Australia."""
    # US states
    assert AddressNormalizer.normalize_state_province("CA", country="United States") == "California"
    assert AddressNormalizer.normalize_state_province("ny", country="USA") == "New York"
    assert (
        AddressNormalizer.normalize_state_province("south carolina", country="US")
        == "South Carolina"
    )
    # Canada
    assert AddressNormalizer.normalize_state_province("bc", country="Canada") == "British Columbia"
    assert AddressNormalizer.normalize_state_province("ON", country="CA") == "Ontario"
    # Australia
    assert (
        AddressNormalizer.normalize_state_province("nsw", country="Australia") == "New South Wales"
    )
    # Fallback / Title casing
    assert AddressNormalizer.normalize_state_province("bavaria", country="Germany") == "Bavaria"
    assert AddressNormalizer.normalize_state_province(None) is None
    assert AddressNormalizer.normalize_state_province("   ") is None


def test_normalize_address_record():
    """Verifies full AddressRecord normalization and trimming."""
    rec = AddressRecord(
        street=" 123 Main St ",
        city=" springfield ",
        state_province=" il ",
        country=" usa ",
        postal_code=" 62701 ",
    )
    norm = AddressNormalizer.normalize_address(rec)
    assert norm.street == "123 Main St"
    assert norm.city == "Springfield"
    assert norm.state_province == "Illinois"
    assert norm.country == "United States"
    assert norm.postal_code == "62701"


def test_normalize_addresses_list():
    """Verifies list normalization with multi-country POIs."""
    records = [
        AddressRecord(state_province="misiones", country="ar"),
        AddressRecord(state_province="paraná", country="brasil"),
    ]
    normalized = AddressNormalizer.normalize_addresses(records)
    assert len(normalized) == 2
    assert normalized[0].country == "Argentina"
    assert normalized[1].country == "Brazil"
