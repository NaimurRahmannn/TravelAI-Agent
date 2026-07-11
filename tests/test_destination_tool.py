import unittest
from unittest.mock import Mock, patch

from app.tools.destination_tool import (
    build_destination_info,
    fetch_country_basics,
    fetch_destination_location,
    fetch_wikipedia_summary,
    get_destination_info,
    infer_best_time_to_visit,
    infer_cost_level,
    infer_travel_styles,
)


class DestinationToolTests(unittest.TestCase):
    @patch("app.tools.destination_tool.httpx.get")
    def test_fetch_destination_location_uses_open_meteo(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "results": [
                {
                    "name": "Tokyo",
                    "country": "Japan",
                    "country_code": "JP",
                    "latitude": 35.6895,
                    "longitude": 139.6917,
                    "timezone": "Asia/Tokyo",
                    "population": 8336599,
                }
            ]
        }
        mock_get.return_value = response

        location = fetch_destination_location("Tokyo")

        self.assertEqual(location["name"], "Tokyo")
        self.assertEqual(location["country"], "Japan")
        self.assertEqual(location["country_code"], "JP")
        self.assertEqual(location["latitude"], 35.6895)
        response.raise_for_status.assert_called_once()

    @patch("app.tools.destination_tool.httpx.get")
    def test_fetch_country_basics_formats_countriesnow_data(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "error": False,
            "msg": "countries and ISO codes retrieved",
            "data": [
                {
                    "name": "Japan",
                    "currency": "JPY",
                    "iso2": "JP",
                    "iso3": "JPN",
                    "dialCode": "+81",
                    "flag": "https://flag.example/jp.png",
                }
            ],
        }
        mock_get.return_value = response

        country = fetch_country_basics("Japan", "JP")

        self.assertEqual(country["name"], "Japan")
        self.assertEqual(country["currencies"][0]["code"], "JPY")
        self.assertEqual(country["languages"], [])
        self.assertEqual(country["calling_code"], "+81")

    @patch("app.tools.destination_tool.httpx.get")
    def test_fetch_wikipedia_summary_handles_page_summary(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "title": "Tokyo",
            "description": "Capital of Japan",
            "extract": "Tokyo is the capital of Japan.",
            "content_urls": {
                "desktop": {
                    "page": "https://en.wikipedia.org/wiki/Tokyo",
                }
            },
        }
        mock_get.return_value = response

        summary = fetch_wikipedia_summary("Tokyo")

        self.assertEqual(summary["title"], "Tokyo")
        self.assertEqual(summary["summary"], "Tokyo is the capital of Japan.")
        self.assertEqual(
            summary["url"],
            "https://en.wikipedia.org/wiki/Tokyo",
        )

    @patch("app.tools.destination_tool.fetch_geoapify_places")
    @patch("app.tools.destination_tool.fetch_wikipedia_summary")
    @patch("app.tools.destination_tool.fetch_country_basics")
    @patch("app.tools.destination_tool.fetch_destination_location")
    def test_build_destination_info_combines_live_and_local_data(
        self,
        mock_location,
        mock_country,
        mock_wikipedia,
        mock_places,
    ):
        mock_location.return_value = {
            "name": "Tokyo",
            "country": "Japan",
            "country_code": "JP",
            "latitude": 35.6895,
            "longitude": 139.6917,
            "timezone": "Asia/Tokyo",
            "population": 8336599,
        }
        mock_country.return_value = {
            "name": "Japan",
            "currencies": [{"code": "JPY"}],
            "languages": ["Japanese"],
        }
        mock_wikipedia.return_value = {
            "title": "Tokyo",
            "summary": "Tokyo is the capital of Japan.",
            "url": "https://en.wikipedia.org/wiki/Tokyo",
        }
        mock_places.return_value = {
            "provider": "geoapify",
            "api_used": True,
            "status": "used",
            "attractions": [{"name": "Tokyo Tower"}],
            "restaurants": [{"name": "Example Ramen"}],
            "hotels": [{"name": "Example Hotel"}],
        }

        info = build_destination_info("Tokyo")

        self.assertEqual(info["destination"], "Tokyo")
        self.assertEqual(info["summary"], "Tokyo is the capital of Japan.")
        self.assertEqual(info["country"]["name"], "Japan")
        self.assertEqual(info["cost_level"], "moderate_to_expensive")
        self.assertIn("city", info["travel_styles"])
        self.assertIn("food", info["travel_styles"])
        self.assertEqual(info["planning_confidence"], "high")
        self.assertEqual(info["places"]["attractions"][0]["name"], "Tokyo Tower")
        self.assertEqual(info["sources"]["geocoding"]["status"], "used")
        self.assertEqual(info["sources"]["country"]["status"], "used")
        self.assertEqual(info["sources"]["wikipedia"]["status"], "used")

    @patch("app.tools.destination_tool.fetch_wikipedia_summary", return_value=None)
    @patch("app.tools.destination_tool.fetch_country_basics", return_value=None)
    @patch("app.tools.destination_tool.fetch_destination_location", return_value=None)
    def test_build_destination_info_falls_back_when_live_data_missing(
        self,
        mock_location,
        mock_country,
        mock_wikipedia,
    ):
        info = build_destination_info("Unknown City")

        self.assertEqual(info["destination"], "Unknown City")
        self.assertIn("Unknown City can be planned", info["summary"])
        self.assertIsNone(info["location"])
        self.assertEqual(info["places"]["status"], "missing_location")
        self.assertEqual(info["planning_confidence"], "low")

    def test_get_destination_info_langchain_tool_invokes(self):
        with patch(
            "app.tools.destination_tool.build_destination_info",
            return_value={"destination": "Tokyo"},
        ):
            result = get_destination_info.invoke(
                {
                    "destination": "Tokyo",
                    "include_places": False,
                }
            )

        self.assertEqual(result, {"destination": "Tokyo"})

    def test_infer_best_time_to_visit_uses_hemisphere(self):
        self.assertEqual(
            infer_best_time_to_visit({"latitude": 35.0}),
            ["April-June", "September-November"],
        )
        self.assertEqual(
            infer_best_time_to_visit({"latitude": -34.0}),
            ["March-May", "September-November"],
        )

    def test_infer_cost_level_uses_currency_signal(self):
        self.assertEqual(
            infer_cost_level({"currencies": [{"code": "BDT"}]}),
            "budget_to_moderate",
        )
        self.assertEqual(
            infer_cost_level({"currencies": [{"code": "JPY"}]}),
            "moderate_to_expensive",
        )

    def test_infer_travel_styles_uses_summary_and_place_categories(self):
        styles = infer_travel_styles(
            "A capital city with historic museums and food markets.",
            {"catering.restaurant", "tourism.sights"},
        )

        self.assertIn("city", styles)
        self.assertIn("culture", styles)
        self.assertIn("food", styles)


if __name__ == "__main__":
    unittest.main()
