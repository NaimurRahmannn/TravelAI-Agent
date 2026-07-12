from app.tools.budget import estimate_travel_budget
from app.tools.currency import convert_currency
from app.tools.destination_tool import get_destination_info
from app.tools.maps import (
    cluster_places,
    find_nearby_places,
    geocode_place,
    get_route,
    map_bounds,
    reverse_geocode,
    travel_time_matrix,
)
from app.tools.weather import get_current_weather


TRAVEL_TOOLS = [
    get_destination_info,
    estimate_travel_budget,
    convert_currency,
    get_current_weather,
    geocode_place,
    reverse_geocode,
    get_route,
    find_nearby_places,
    cluster_places,
    travel_time_matrix,
    map_bounds,
]

TRAVEL_TOOL_NAMES = tuple(tool.name for tool in TRAVEL_TOOLS)
