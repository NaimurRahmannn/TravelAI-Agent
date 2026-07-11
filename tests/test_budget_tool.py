import unittest
from unittest.mock import Mock, patch

from app.tools.budget import (
    apply_aviationstack_flight_data,
    apply_free_cost_of_living_data,
    apply_live_travel_prices,
    build_budget_estimate,
    estimate_travel_budget,
    fetch_exchange_rate,
)


class BudgetToolTests(unittest.TestCase):
    def test_build_budget_estimate_returns_category_breakdown(self):
        estimate = build_budget_estimate(
            destination="Tokyo",
            duration_days=5,
            travelers=2,
            style="standard",
        )

        self.assertEqual(estimate["destination"], "Tokyo")
        self.assertEqual(estimate["currency"], "USD")
        self.assertEqual(estimate["pricing_source"], "local_usd_rates")
        self.assertEqual(
            estimate["categories"],
            {
                "lodging": 750.0,
                "food": 350.0,
                "transport": 200.0,
                "activities": 250.0,
            },
        )
        self.assertEqual(estimate["contingency"], 155.0)
        self.assertEqual(estimate["estimated_total"], 1705.0)
        self.assertEqual(estimate["per_person"], 852.5)
        self.assertEqual(estimate["per_day"], 341.0)

    def test_build_budget_estimate_compares_against_available_budget(self):
        estimate = build_budget_estimate(
            destination="Bangkok",
            duration_days=4,
            travelers=1,
            style="budget",
            total_budget=350,
        )

        self.assertEqual(estimate["estimated_total"], 330.0)
        self.assertEqual(estimate["available_budget"], 350.0)
        self.assertEqual(estimate["difference"], 20.0)
        self.assertEqual(estimate["status"], "within_budget")

    def test_build_budget_estimate_reports_over_budget(self):
        estimate = build_budget_estimate(
            destination="Paris",
            duration_days=3,
            travelers=2,
            style="premium",
            total_budget=1500,
        )

        self.assertEqual(estimate["status"], "over_budget")
        self.assertEqual(estimate["difference"], -744.0)

    def test_build_budget_estimate_rejects_invalid_duration(self):
        with self.assertRaisesRegex(ValueError, "duration_days"):
            build_budget_estimate(
                destination="Rome",
                duration_days=0,
                travelers=1,
            )

    def test_estimate_travel_budget_langchain_tool_invokes(self):
        result = estimate_travel_budget.invoke(
            {
                "destination": "Kyoto",
                "duration_days": 2,
                "travelers": 2,
                "style": "budget",
                "currency": "USD",
                "total_budget": 300,
                "use_free_cost_data": False,
                "use_aviationstack": False,
            }
        )

        self.assertEqual(result["estimated_total"], 330.0)
        self.assertEqual(result["status"], "over_budget")
        self.assertFalse(result["api_used"])
        self.assertEqual(
            result["live_pricing"]["status"],
            "no_key_free_mode",
        )
        self.assertEqual(result["live_pricing"]["provider"], "free_estimate")

    @patch("app.tools.budget.httpx.get")
    def test_fetch_exchange_rate_uses_currency_api(self, mock_get):
        response = Mock()
        response.json.return_value = {"rate": 120.5}
        mock_get.return_value = response

        rate = fetch_exchange_rate("usd", "bdt")

        self.assertEqual(rate, 120.5)
        mock_get.assert_called_once_with(
            "https://api.frankfurter.dev/v2/rate/USD/BDT",
            timeout=10,
        )
        response.raise_for_status.assert_called_once()

    @patch("app.tools.budget.fetch_exchange_rate", return_value=100)
    def test_estimate_travel_budget_converts_with_live_rate(self, mock_rate):
        result = estimate_travel_budget.invoke(
            {
                "destination": "Kyoto",
                "duration_days": 2,
                "travelers": 2,
                "style": "budget",
                "currency": "BDT",
                "total_budget": 40000,
                "use_free_cost_data": False,
                "use_aviationstack": False,
            }
        )

        self.assertEqual(result["currency"], "BDT")
        self.assertEqual(result["source_currency"], "USD")
        self.assertEqual(result["exchange_rate"], 100)
        self.assertTrue(result["api_used"])
        self.assertEqual(result["estimated_total"], 33000.0)
        self.assertEqual(result["available_budget"], 40000.0)
        self.assertEqual(result["difference"], 7000.0)
        self.assertEqual(result["status"], "within_budget")
        mock_rate.assert_called_once_with("USD", "BDT")

    @patch("app.tools.budget.AmadeusClient")
    def test_apply_live_travel_prices_replaces_flight_and_hotel_costs(
        self,
        mock_client_class,
    ):
        client = Mock()
        client.is_configured = True
        client.get_lowest_flight_price.return_value = {
            "amount": 500.0,
            "currency": "USD",
            "origin": "DAC",
            "destination": "TYO",
            "offer_id": "flight-1",
        }
        client.get_lowest_hotel_price.return_value = {
            "amount": 600.0,
            "currency": "USD",
            "hotel_id": "hotel-1",
            "offer_id": "hotel-offer-1",
        }
        mock_client_class.return_value = client
        estimate = build_budget_estimate(
            destination="Tokyo",
            duration_days=5,
            travelers=2,
            style="standard",
        )

        result = apply_live_travel_prices(
            estimate=estimate,
            destination="Tokyo",
            duration_days=5,
            travelers=2,
            origin="Dhaka",
            travel_date="2026-10-01",
            return_date="2026-10-06",
        )

        self.assertEqual(result["categories"]["flights"], 500.0)
        self.assertEqual(result["categories"]["lodging"], 600.0)
        self.assertTrue(result["live_pricing"]["api_used"])
        self.assertEqual(result["live_pricing"]["flight"]["status"], "used")
        self.assertEqual(result["live_pricing"]["hotel"]["status"], "used")
        self.assertEqual(result["estimated_total"], 2090.0)
        client.get_lowest_flight_price.assert_called_once_with(
            origin="Dhaka",
            destination="Tokyo",
            departure_date="2026-10-01",
            return_date="2026-10-06",
            adults=2,
        )
        client.get_lowest_hotel_price.assert_called_once_with(
            destination="Tokyo",
            check_in_date="2026-10-01",
            check_out_date="2026-10-06",
            adults=2,
        )

    @patch("app.tools.budget.AmadeusClient")
    def test_apply_live_travel_prices_reports_missing_credentials(
        self,
        mock_client_class,
    ):
        client = Mock()
        client.is_configured = False
        mock_client_class.return_value = client
        estimate = build_budget_estimate(
            destination="Tokyo",
            duration_days=5,
            travelers=2,
            style="standard",
        )

        result = apply_live_travel_prices(
            estimate=estimate,
            destination="Tokyo",
            duration_days=5,
            travelers=2,
            origin="Dhaka",
            travel_date="2026-10-01",
            return_date="2026-10-06",
        )

        self.assertFalse(result["live_pricing"]["api_used"])
        self.assertEqual(
            result["live_pricing"]["status"],
            "credentials_missing",
        )

    def test_estimate_travel_budget_can_explicitly_request_amadeus_path(self):
        result = estimate_travel_budget.invoke(
            {
                "destination": "Kyoto",
                "duration_days": 2,
                "travelers": 2,
                "style": "budget",
                "currency": "USD",
                "use_live_travel_prices": True,
                "use_free_cost_data": False,
                "use_aviationstack": False,
            }
        )

        self.assertFalse(result["live_pricing"]["api_used"])
        self.assertEqual(
            result["live_pricing"]["status"],
            "credentials_missing",
        )

    @patch("app.tools.budget.fetch_teleport_cost_profile")
    def test_apply_free_cost_of_living_data_adjusts_local_categories(
        self,
        mock_cost_profile,
    ):
        mock_cost_profile.return_value = {
            "provider": "teleport",
            "city": "Tokyo, Japan",
            "score_out_of_10": 6.5,
            "expense_multiplier": 0.8,
        }
        estimate = build_budget_estimate(
            destination="Tokyo",
            duration_days=5,
            travelers=2,
            style="standard",
        )

        result = apply_free_cost_of_living_data(
            estimate=estimate,
            destination="Tokyo",
        )

        self.assertEqual(result["categories"]["lodging"], 600.0)
        self.assertEqual(result["categories"]["food"], 280.0)
        self.assertEqual(result["categories"]["transport"], 160.0)
        self.assertEqual(result["categories"]["activities"], 200.0)
        self.assertEqual(result["estimated_total"], 1364.0)
        self.assertTrue(result["free_cost_data"]["api_used"])
        self.assertEqual(result["free_cost_data"]["status"], "used")

    @patch("app.tools.budget.fetch_teleport_cost_profile", return_value=None)
    def test_apply_free_cost_of_living_data_keeps_estimate_without_city_data(
        self,
        mock_cost_profile,
    ):
        estimate = build_budget_estimate(
            destination="Unknown Place",
            duration_days=5,
            travelers=2,
            style="standard",
        )

        result = apply_free_cost_of_living_data(
            estimate=estimate,
            destination="Unknown Place",
        )

        self.assertEqual(result["estimated_total"], 1705.0)
        self.assertFalse(result["free_cost_data"]["api_used"])
        self.assertEqual(
            result["free_cost_data"]["status"],
            "no_city_cost_data",
        )

    @patch("app.tools.budget.AviationstackClient")
    def test_apply_aviationstack_flight_data_adds_estimated_flights(
        self,
        mock_client_class,
    ):
        client = Mock()
        client.is_configured = True
        client.get_route_flights.return_value = {
            "count": 2,
            "sample_flights": [
                {
                    "flight_date": "2026-10-01",
                    "flight_status": "scheduled",
                    "airline": "Example Air",
                    "flight_number": "EX123",
                }
            ],
        }
        mock_client_class.return_value = client
        estimate = build_budget_estimate(
            destination="DAC",
            duration_days=5,
            travelers=2,
            style="standard",
        )

        result = apply_aviationstack_flight_data(
            estimate=estimate,
            origin="JFK",
            destination="DAC",
            travel_date="2026-10-01",
        )

        self.assertEqual(result["categories"]["flights"], 900.0)
        self.assertEqual(result["flight_data"]["provider"], "aviationstack")
        self.assertTrue(result["flight_data"]["api_used"])
        self.assertEqual(result["flight_data"]["status"], "used")
        self.assertEqual(result["estimated_total"], 2695.0)
        client.get_route_flights.assert_called_once_with(
            origin="JFK",
            destination="DAC",
            flight_date="2026-10-01",
        )

    def test_apply_aviationstack_flight_data_requires_iata_codes(self):
        estimate = build_budget_estimate(
            destination="Dhaka",
            duration_days=5,
            travelers=2,
            style="standard",
        )

        result = apply_aviationstack_flight_data(
            estimate=estimate,
            origin="New York",
            destination="Dhaka",
            travel_date="2026-10-01",
        )

        self.assertFalse(result["flight_data"]["api_used"])
        self.assertEqual(
            result["flight_data"]["status"],
            "requires_iata_codes",
        )


if __name__ == "__main__":
    unittest.main()
