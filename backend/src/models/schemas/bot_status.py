import pydantic


class BotStatusBatchIn(pydantic.BaseModel):
    """Body forwarded as-is to the bot's POST /api/manager/bot_status/batch."""

    phones: list[str] = pydantic.Field(min_length=1)


class BotStatusToggleOut(pydantic.BaseModel):
    phone: str
    paused: bool
