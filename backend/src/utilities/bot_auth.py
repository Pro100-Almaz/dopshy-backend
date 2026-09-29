import os

from src.config.manager import settings


def get_bot_service_token() -> str:
    """Resolve the bot credential while supporting legacy deployments."""
    return (
        os.getenv("BOT_SERVICE_TOKEN")
        or settings.BOT_SERVICE_TOKEN
        or os.getenv("X_SERVICE_TOKEN")
        or os.getenv("MANAGER_API_KEY")
        or settings.MANAGER_API_KEY
        or ""
    )


def get_bot_service_headers(*, json: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "X-API-Key": get_bot_service_token(),
    }
    if json:
        headers["Content-Type"] = "application/json"
    return headers
