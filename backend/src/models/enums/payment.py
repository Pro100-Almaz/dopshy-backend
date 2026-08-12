import enum


class PaymentStatus(str, enum.Enum):
    """Lifecycle of an ApiPay invoice.

    ApiPay drives every value except ``CREATED``, which is local-only: the row is
    inserted before the ApiPay call so a crash mid-request still leaves a trace.
    Documented lifecycle: processing → pending → paid (or cancelled / expired / error).
    """

    CREATED = "created"
    PROCESSING = "processing"
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ERROR = "error"


#: Statuses meaning "money has arrived" — these are the ones the bot must learn about.
SETTLED_PAYMENT_STATUSES: frozenset[str] = frozenset(
    {
        PaymentStatus.PAID.value,
        PaymentStatus.PARTIALLY_REFUNDED.value,
        PaymentStatus.REFUNDED.value,
    }
)

#: Statuses ApiPay will never move away from — no point polling them again.
TERMINAL_PAYMENT_STATUSES: frozenset[str] = frozenset(
    {
        PaymentStatus.REFUNDED.value,
        PaymentStatus.CANCELLED.value,
        PaymentStatus.EXPIRED.value,
        PaymentStatus.ERROR.value,
    }
)
