from app.schemas.trip import TripPreferences


class ClarificationService:
    QUESTIONS = {
        "destination": "Where would you like to travel?",
        "travel_date": "When are you planning to travel?",
        "budget": "What is your approximate travel budget?",
        "travelers": "How many people are traveling?",
        "duration_days":"How many days are you planning to travel?"
    }

    def get_next_question(
        self,
        trip_preferences: TripPreferences,
    ) -> str | None:
        missing_fields = (
            trip_preferences.get_missing_fields()
        )

        if not missing_fields:
            return None

        next_field = missing_fields[0]

        return self.QUESTIONS[next_field]