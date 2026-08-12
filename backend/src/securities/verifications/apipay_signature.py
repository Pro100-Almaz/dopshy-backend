import hashlib
import hmac


def compute_webhook_signature(raw_body: bytes, secret: str) -> str:
    """Build the `sha256=<hex>` value ApiPay puts in `X-Webhook-Signature`."""
    digest = hmac.new(key=secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """Check an ApiPay webhook signature in constant time.

    `raw_body` MUST be the untouched request body. Re-serialising the parsed JSON
    changes key order and whitespace, and the HMAC will never match — this is the
    single most common way this integration breaks.
    """
    if not signature or not secret:
        return False
    expected = compute_webhook_signature(raw_body=raw_body, secret=secret)
    return hmac.compare_digest(expected, signature)
