"""Tests for app.tools.maps — movement and location intelligence.

Covers geocoding, reverse geocoding, routing, nearby search,
place clustering, travel time matrix, and map bounds.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.tools.maps import (
    _format_duration,
    _haversine,
    _parse_coords,
    cluster_places_by_distance,
    compute_map_bounds,
    compute_travel_time_matrix,
    find_nearby_places_internal,
    geocode_place_internal,
    get_route_internal,
    reverse_geocode_internal,
)

# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_zero_distance(self):
        assert _haversine(0, 0, 0, 0) == 0.0

    def test_known_distance(self):
        # New York (40.7128, -74.006) -> London (51.5074, -0.1278) ≈ 5570 km
        dist = _haversine(40.7128, -74.006, 51.5074, -0.1278)
        assert 5500 < dist < 5600

    def test_short_distance(self):
        # ~111 km for 1 degree of latitude at the equator
        dist = _haversine(0, 0, 1, 0)
        assert 110 < dist < 112


# ---------------------------------------------------------------------------
# Parse coords
# ---------------------------------------------------------------------------


class TestParseCoords:
    def test_valid(self):
        assert _parse_coords("40.7128,-74.006") == (40.7128, -74.006)

    def test_with_spaces(self):
        assert _parse_coords(" 40.7128 , -74.006 ") == (40.7128, -74.006)

    def test_invalid_text(self):
        assert _parse_coords("New York") is None

    def test_too_many_parts(self):
        assert _parse_coords("1,2,3") is None


# ---------------------------------------------------------------------------
# Format duration
# ---------------------------------------------------------------------------


class TestFormatDuration:
    def test_minutes_only(self):
        assert _format_duration(1500) == "25 min"

    def test_hours_and_minutes(self):
        assert _format_duration(5400) == "1 hr 30 min"

    def test_exact_hours(self):
        assert _format_duration(7200) == "2 hr"

    def test_zero(self):
        assert _format_duration(0) == "0 min"


# ---------------------------------------------------------------------------
# Geocode (mocked)
# ---------------------------------------------------------------------------


def _mock_geocode_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "formatted": "Dhaka, Bangladesh",
                "lat": 23.8103,
                "lon": 90.4125,
                "city": "Dhaka",
                "state": "Dhaka Division",
                "country": "Bangladesh",
                "country_code": "bd",
                "postcode": "1000",
                "result_type": "city",
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestGeocode:
    @patch("app.tools.maps.httpx.get", return_value=_mock_geocode_response())
    def test_geocode_success(self, mock_get):
        result = geocode_place_internal("Dhaka")
        assert result["status"] == "found"
        assert result["latitude"] == 23.8103
        assert result["longitude"] == 90.4125
        assert result["city"] == "Dhaka"
        assert result["country"] == "Bangladesh"
        assert result["provider"] == "geoapify"

    @patch("app.tools.maps.httpx.get")
    def test_geocode_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = geocode_place_internal("xyznonexistent")
        assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# Reverse geocode (mocked)
# ---------------------------------------------------------------------------


def _mock_reverse_response():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "formatted": "Motijheel, Dhaka 1000, Bangladesh",
                "city": "Dhaka",
                "state": "Dhaka Division",
                "country": "Bangladesh",
                "country_code": "bd",
                "postcode": "1000",
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestReverseGeocode:
    @patch(
        "app.tools.maps.httpx.get",
        return_value=_mock_reverse_response(),
    )
    def test_reverse_success(self, mock_get):
        result = reverse_geocode_internal(23.8103, 90.4125)
        assert result["status"] == "found"
        assert result["city"] == "Dhaka"
        assert result["country"] == "Bangladesh"


# ---------------------------------------------------------------------------
# Routing (mocked)
# ---------------------------------------------------------------------------


def _mock_route_response():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "features": [
            {
                "properties": {
                    "distance": 15000,  # 15 km
                    "time": 1800,  # 30 min
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestRouting:
    @patch("app.tools.maps.httpx.get", return_value=_mock_route_response())
    def test_route_with_coords(self, mock_get):
        result = get_route_internal(
            origin="23.8103,90.4125",
            destination="23.7500,90.3750",
            mode="drive",
        )
        assert result["status"] == "found"
        assert result["distance_km"] == 15.0
        assert result["duration_minutes"] == 30.0
        assert result["mode"] == "drive"
        assert result["straight_line_km"] > 0

    @patch("app.tools.maps.httpx.get")
    def test_route_no_route_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"features": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = get_route_internal(
            origin="0.0,0.0",
            destination="0.1,0.1",
            mode="drive",
        )
        assert result["status"] == "no_route"


# ---------------------------------------------------------------------------
# Nearby search (mocked)
# ---------------------------------------------------------------------------


def _mock_places_response():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "features": [
            {
                "properties": {
                    "name": "Hazrat Shahjalal International Airport",
                    "formatted": "Dhaka, Bangladesh",
                    "lat": 23.8500,
                    "lon": 90.4000,
                    "categories": ["airport"],
                    "distance": 3200,
                    "city": "Dhaka",
                    "country": "Bangladesh",
                    "country_code": "bd",
                },
                "geometry": {"coordinates": [90.4000, 23.8500]},
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestNearbySearch:
    @patch(
        "app.tools.maps.httpx.get",
        return_value=_mock_places_response(),
    )
    def test_nearby_airport(self, mock_get):
        result = find_nearby_places_internal(
            latitude=23.8103,
            longitude=90.4125,
            category="airport",
            radius_meters=10000,
        )
        assert result["status"] == "found"
        assert result["count"] == 1
        assert result["places"][0]["name"] == (
            "Hazrat Shahjalal International Airport"
        )

    @patch("app.tools.maps.httpx.get")
    def test_nearby_no_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"features": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = find_nearby_places_internal(
            latitude=0.0,
            longitude=0.0,
            category="hospital",
        )
        assert result["status"] == "no_results"
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# Clustering (pure logic, no mocking needed)
# ---------------------------------------------------------------------------


class TestClustering:
    def test_empty_list(self):
        result = cluster_places_by_distance([], max_cluster_radius_km=3.0)
        assert result["count"] == 0
        assert result["clusters"] == []

    def test_single_place(self):
        places = [
            {"name": "A", "latitude": 23.81, "longitude": 90.41}
        ]
        result = cluster_places_by_distance(places)
        assert result["count"] == 1
        assert result["clusters"][0]["place_count"] == 1

    def test_nearby_places_cluster_together(self):
        places = [
            {"name": "A", "latitude": 23.810, "longitude": 90.410},
            {"name": "B", "latitude": 23.812, "longitude": 90.412},
            {"name": "C", "latitude": 23.815, "longitude": 90.415},
        ]
        result = cluster_places_by_distance(
            places, max_cluster_radius_km=5.0,
        )
        # All three should be in one cluster since they're very close
        assert result["count"] == 1
        assert result["clusters"][0]["place_count"] == 3

    def test_distant_places_separate_clusters(self):
        places = [
            {"name": "Dhaka", "latitude": 23.81, "longitude": 90.41},
            {"name": "Chittagong", "latitude": 22.35, "longitude": 91.78},
        ]
        result = cluster_places_by_distance(
            places, max_cluster_radius_km=5.0,
        )
        assert result["count"] == 2

    def test_suggestion_text(self):
        places = [
            {"name": "A", "latitude": 23.81, "longitude": 90.41},
            {"name": "B", "latitude": 22.35, "longitude": 91.78},
            {"name": "C", "latitude": 24.90, "longitude": 91.87},
        ]
        result = cluster_places_by_distance(
            places, max_cluster_radius_km=3.0,
        )
        assert "3 efficient day" in result["suggestion"]


# ---------------------------------------------------------------------------
# Map bounds (pure logic)
# ---------------------------------------------------------------------------


class TestMapBounds:
    def test_empty(self):
        result = compute_map_bounds([])
        assert result["status"] == "no_places"

    def test_single_point(self):
        places = [{"latitude": 23.81, "longitude": 90.41}]
        result = compute_map_bounds(places)
        assert result["center"]["latitude"] == 23.81
        assert result["center"]["longitude"] == 90.41
        assert result["suggested_zoom"] == 16  # very tight span

    def test_bounding_box(self):
        places = [
            {"latitude": 23.0, "longitude": 90.0},
            {"latitude": 24.0, "longitude": 91.0},
        ]
        result = compute_map_bounds(places)
        bb = result["bounding_box"]
        assert bb["south_west"]["latitude"] == 23.0
        assert bb["north_east"]["latitude"] == 24.0
        assert bb["south_west"]["longitude"] == 90.0
        assert bb["north_east"]["longitude"] == 91.0
        assert result["center"]["latitude"] == 23.5
        assert result["center"]["longitude"] == 90.5

    def test_zoom_levels(self):
        # Wide span → low zoom
        places = [
            {"latitude": 0.0, "longitude": 0.0},
            {"latitude": 30.0, "longitude": 30.0},
        ]
        result = compute_map_bounds(places)
        assert result["suggested_zoom"] <= 6


# ---------------------------------------------------------------------------
# Travel time matrix (mocked)
# ---------------------------------------------------------------------------


class TestTravelTimeMatrix:
    def test_single_place(self):
        places = [{"name": "A", "latitude": 23.81, "longitude": 90.41}]
        result = compute_travel_time_matrix(places)
        assert result["status"] == "need_at_least_2_places"

    def test_large_list_uses_straight_line(self):
        # 9 places → should use straight_line_estimate
        places = [
            {"name": f"P{i}", "latitude": 23.0 + i * 0.1, "longitude": 90.0}
            for i in range(9)
        ]
        result = compute_travel_time_matrix(places, mode="drive")
        assert result["source"] == "straight_line_estimate"
        assert result["pair_count"] == 36  # C(9,2) = 36

    @patch("app.tools.maps.httpx.get", return_value=_mock_route_response())
    def test_small_list_uses_api(self, mock_get):
        places = [
            {"name": "A", "latitude": 23.81, "longitude": 90.41},
            {"name": "B", "latitude": 23.82, "longitude": 90.42},
        ]
        result = compute_travel_time_matrix(places, mode="drive")
        assert result["source"] == "routing_api"
        assert result["pair_count"] == 1
        assert result["matrix"][0]["from"] == "A"
        assert result["matrix"][0]["to"] == "B"
