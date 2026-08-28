import datetime
import enum

import pydantic


class DocumentBotType(str, enum.Enum):
    ARENA = "arena"
    BOX_ACADEMY = "box_academy"
    FS_ACADEMY = "fs_academy"


class DocumentExtractIn(pydantic.BaseModel):
    bot_type: DocumentBotType
    start_date: datetime.date
    end_date: datetime.date

    @pydantic.model_validator(mode="after")
    def validate_period(self) -> "DocumentExtractIn":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("Document extraction period cannot exceed 366 days.")
        return self
