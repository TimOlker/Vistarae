-- Copyright (c) 2026 Tim Olker
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.
--
-- SPDX-License-Identifier: Apache-2.0

-- Starter seed test data for Vistarae
-- Creates sample demo user, lists, macro-sites, and child POIs with access points

-- 1. Demo User (email: demo@vistarae.com, password: Traveler123!)
INSERT INTO users (id, email, hashed_password, full_name, is_active) VALUES
(
    '00000000-0000-0000-0000-000000000001',
    'demo@vistarae.com',
    '$2b$12$ZHu4T5bcqXEUFWiTvaEwOuEC2/zTNyhDm4cEvRWCPgiYGKmxg5I5O',
    'Demo Traveler',
    true
) ON CONFLICT (id) DO NOTHING;

-- 2. Lists (owned by demo user)
INSERT INTO lists (id, user_id, title, description, is_trip) VALUES
('11111111-1111-1111-1111-111111111111', '00000000-0000-0000-0000-000000000001', 'California Sierra Roadtrip', 'Top photo spots and scenic trails across the Sierra Nevada.', true),
('22222222-2222-2222-2222-222222222222', '00000000-0000-0000-0000-000000000001', 'Iconic National Park Overlooks', 'World-class viewpoints and golden hour vantage points.', false)
ON CONFLICT (id) DO NOTHING;

-- 3. Macro POI: Yosemite National Park (Site to see)
INSERT INTO pois (
    id, user_id, name, name_aliases, poi_type, personal_rating, description, category_tags,
    location, geofence_radius_ft, physical_effort, booking_lead_time, indoor_outdoor,
    estimated_duration, cost_tier, best_time_to_visit, source_url, source_type,
    iptc_sublocation, iptc_city, iptc_province_state, iptc_country_code, iptc_world_region
) VALUES (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    '00000000-0000-0000-0000-000000000001',
    'Yosemite National Park',
    ARRAY['Yosemite Valley', 'Yosemite'],
    'site to see',
    5,
    'Iconic glacial valley in California’s Sierra Nevada mountains renowned for giant sequoias and granite cliffs.',
    ARRAY['national park', 'scenic', 'hiking', 'nature'],
    ST_SetSRID(ST_MakePoint(-119.5383, 37.8651), 4326)::geography,
    52800, -- 10 mile radius
    'drive-up',
    'months ahead',
    'Outdoor',
    'full day',
    '$$',
    'Sunrise / Golden Hour',
    'https://www.nps.gov/yose',
    'Official Site',
    'Yosemite Valley',
    'Yosemite Village',
    'California',
    'US',
    'North America'
) ON CONFLICT (id) DO NOTHING;

-- 4. Child POI: Glacier Point Overlook (Photo location nested under Yosemite)
INSERT INTO pois (
    id, user_id, name, name_aliases, poi_type, personal_rating, description, category_tags,
    location, geofence_radius_ft, parent_poi_id, physical_effort, booking_lead_time,
    indoor_outdoor, estimated_duration, cost_tier, best_time_to_visit, source_url, source_type,
    iptc_sublocation, iptc_city, iptc_province_state, iptc_country_code, iptc_world_region
) VALUES (
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    '00000000-0000-0000-0000-000000000001',
    'Glacier Point Overlook',
    ARRAY['Glacier Point'],
    'photo location',
    5,
    'A commanding viewpoint offering breathtaking panoramic vistas of Yosemite Valley, Half Dome, and Yosemite Falls.',
    ARRAY['viewpoint', 'photography', 'half dome', 'sunset'],
    ST_SetSRID(ST_MakePoint(-119.5736, 37.7304), 4326)::geography,
    1000,
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    'paved walk',
    'walk-in ok',
    'Outdoor',
    '1-2 hours',
    'Free',
    'Sunset / Golden Hour',
    'https://www.nps.gov/yose/planyourvisit/glacierpoint.htm',
    'Official Site',
    'Glacier Point Road',
    'Yosemite Village',
    'California',
    'US',
    'North America'
) ON CONFLICT (id) DO NOTHING;

-- 5. Access Point for Glacier Point
INSERT INTO poi_access_points (
    id, poi_id, type, description, location, parking_logistics
) VALUES (
    'cccccccc-cccc-cccc-cccc-cccccccccccc',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'parking lot',
    'Glacier Point Main Parking Lot with gift shop and restrooms.',
    ST_SetSRID(ST_MakePoint(-119.5744, 37.7289), 4326)::geography,
    'free parking'
) ON CONFLICT (id) DO NOTHING;

-- 6. Membership linking Glacier Point to both lists
INSERT INTO poi_list_memberships (poi_id, list_id) VALUES
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11111111-1111-1111-1111-111111111111'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222')
ON CONFLICT (poi_id, list_id) DO NOTHING;
