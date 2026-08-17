import enum


class BookingStatus(str, enum.Enum):
    DRAFT = "draft"
    AWAITING_PAYMENT = "awaiting_payment"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    UNPAID = "unpaid"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class BookingSource(str, enum.Enum):
    LANDING = "landing"
    ACCOUNT = "account"
    MANAGER = "manager"
    CHATBOT = "chatbot"


class RepeatMode(str, enum.Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"