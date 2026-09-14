import pydantic
import typing


BotType = typing.Literal["arena", "football_academy", "boxing_academy"]


class BotStatusBatchIn(pydantic.BaseModel):
    """Body forwarded as-is to the bot's POST /api/manager/bot_status/batch."""

    phones: list[str] = pydantic.Field(min_length=1)


class BotStatusToggleOut(pydantic.BaseModel):
    phone: str
    paused: bool


class BotEnabledStatus(pydantic.BaseModel):
    is_enabled: bool


class BotEnabledStatusIn(pydantic.BaseModel):
    enabled: bool = pydantic.Field(strict=True)
    bot_type: BotType = "arena"
