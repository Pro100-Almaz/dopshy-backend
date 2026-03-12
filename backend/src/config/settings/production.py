import logging

from src.config.settings.base import BackendBaseSettings
from src.config.settings.environment import Environment


class BackendProdSettings(BackendBaseSettings):
    DESCRIPTION: str | None = "Production Environment."
    DEBUG: bool = False
    ENVIRONMENT: Environment = Environment.PRODUCTION
    IS_DB_ECHO_LOG: bool = False
    LOGGING_LEVEL: int = logging.WARNING
