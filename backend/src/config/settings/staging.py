from src.config.settings.base import BackendBaseSettings
from src.config.settings.environment import Environment


class BackendStageSettings(BackendBaseSettings):
    DESCRIPTION: str | None = "Test Environment."
    DEBUG: bool = False
    ENVIRONMENT: Environment = Environment.STAGING
    IS_DB_ECHO_LOG: bool = False
