import fastapi
import httpx
import loguru

from src.config.manager import settings

router = fastapi.APIRouter(prefix="/webhooks", tags=["webhooks"])

#: ApiPay retries anything that is not answered 2xx within five seconds, so the hop
#: to the bot must finish with a margin to spare.
FORWARD_TIMEOUT: float = 4.0


@router.post(path="/apipay", name="webhooks:apipay", include_in_schema=False)
async def apipay_webhook(request: fastapi.Request) -> dict[str, bool]:
    """Payment status notifications from ApiPay.kz.

    This backend keeps no payment state — the bot creates the invoices and owns the
    records — so the body is passed on byte for byte to the bot's `/webhooks/apipay`,
    signature header included, and the bot verifies it and updates its rows.

    Answering 502 on a failed hop is deliberate: ApiPay then redelivers the event
    (11 attempts over ~2 hours) instead of the payment silently going missing.
    """
    raw_body = await request.body()
    print("RAW BODY", raw_body)

    if not settings.BOT_URL:
        loguru.logger.error("ApiPay webhook received but BOT_URL is not configured — nothing to forward to")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY, detail="BOT_URL is not configured."
        )

    url = settings.BOT_URL.rstrip("/") + "/webhooks/apipay"
    headers = {
        "Content-Type": request.headers.get("Content-Type", "application/json"),
        "Accept": "application/json",
        "X-API-KEY": settings.MANAGER_API_KEY,
        # The bot checks this HMAC itself, so it must reach it untouched — which is
        # also why the body is relayed as raw bytes and never re-serialised.
        "X-Webhook-Signature": request.headers.get("X-Webhook-Signature", ""),
    }

    try:
        async with httpx.AsyncClient(timeout=FORWARD_TIMEOUT) as client:
            response = await client.post(url, headers=headers, content=raw_body)
    except httpx.HTTPError as exc:
        loguru.logger.error(f"Could not deliver ApiPay webhook to the bot at {url}: {exc}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY, detail="Bot service is unreachable."
        ) from exc

    if response.status_code >= 400:
        loguru.logger.error(f"Bot rejected the ApiPay webhook: {response.status_code} {response.text[:200]}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY, detail="Bot service rejected the webhook."
        )

    loguru.logger.info(f"ApiPay webhook forwarded to the bot ({response.status_code})")
    return {"ok": True}
