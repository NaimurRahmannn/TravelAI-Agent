from langchain.tools import tool


@tool
def get_destination_info(destination: str) -> str:
    """Get basic travel information about a destination."""

    destination_info = {
        "japan": (
            "Japan is known for Tokyo, Kyoto, Osaka, "
            "temples, local food, and efficient public transport."
        ),
        "italy": (
            "Italy is known for Rome, Florence, Venice,"
            "historic architecture, art, and regional food."
        ),
        "thailand":(
            "Thailand is known for Bangkok, beaches, temples,"
            "street food, and tropical destinations."
        ),
    }

    return destination_info.get(
        destination.lower(),
        f"No destination information found for {destination}.",
    )