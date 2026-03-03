import enum


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class BookingSource(str, enum.Enum):
    LANDING = "landing"
    ACCOUNT = "account"
    MANAGER = "manager"
    CHATBOT = "chatbot"
