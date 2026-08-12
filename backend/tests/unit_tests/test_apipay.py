import hashlib
import hmac
import json

import pytest

from src.securities.verifications.apipay_signature import compute_webhook_signature, verify_webhook_signature
from src.services.apipay import ApiPayClient, normalize_kz_phone

SECRET = "test-webhook-secret"


class TestNormalizeKzPhone:
    @pytest.mark.parametrize(
        "raw",
        [
            "87001234567",
            "+7 700 123 45 67",
            "77001234567",
            "7001234567",
            "+7 (700) 123-45-67",
        ],
    )
    def test_accepts_every_shape_people_type(self, raw: str) -> None:
        assert normalize_kz_phone(raw) == "87001234567"

    @pytest.mark.parametrize("raw", ["123", "", "8700123456", "870012345678", "12345678901"])
    def test_rejects_anything_kaspi_would_422(self, raw: str) -> None:
        with pytest.raises(ValueError):
            normalize_kz_phone(raw)


class TestWebhookSignature:
    def test_matches_apipay_reference_hmac(self) -> None:
        body = json.dumps({"event": "invoice.status_changed"}).encode()
        expected = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        assert compute_webhook_signature(raw_body=body, secret=SECRET) == expected
        assert verify_webhook_signature(raw_body=body, signature=expected, secret=SECRET) is True

    def test_rejects_tampered_body(self) -> None:
        body = b'{"event":"invoice.status_changed","invoice":{"amount":"100.00"}}'
        signature = compute_webhook_signature(raw_body=body, secret=SECRET)
        tampered = b'{"event":"invoice.status_changed","invoice":{"amount":"999999.00"}}'
        assert verify_webhook_signature(raw_body=tampered, signature=signature, secret=SECRET) is False

    def test_rejects_wrong_secret(self) -> None:
        body = b'{"event":"webhook.test"}'
        signature = compute_webhook_signature(raw_body=body, secret="other-secret")
        assert verify_webhook_signature(raw_body=body, signature=signature, secret=SECRET) is False

    @pytest.mark.parametrize("signature", [None, "", "sha256=", "garbage"])
    def test_rejects_missing_or_malformed_header(self, signature: str | None) -> None:
        assert verify_webhook_signature(raw_body=b"{}", signature=signature, secret=SECRET) is False

    def test_rejects_when_secret_is_unset(self) -> None:
        """An unconfigured deployment must never accept unverified payment events."""
        body = b'{"event":"webhook.test"}'
        assert verify_webhook_signature(raw_body=body, signature="sha256=abc", secret="") is False

    def test_signature_is_computed_over_raw_bytes_not_reserialised_json(self) -> None:
        """Re-serialising the parsed JSON changes whitespace and breaks the HMAC —
        the single most common way this integration silently fails."""
        raw = b'{"event": "webhook.test",  "n": 1}'
        signature = compute_webhook_signature(raw_body=raw, secret=SECRET)
        reserialised = json.dumps(json.loads(raw), separators=(",", ":")).encode()
        assert verify_webhook_signature(raw_body=reserialised, signature=signature, secret=SECRET) is False


class TestApiPayErrorExtraction:
    def test_reads_error_code_slug(self) -> None:
        code, message, meta = ApiPayClient._extract_error(
            {"error": "kaspi_session_not_configured", "message": "Cashier not connected"}, 400
        )
        assert code == "kaspi_session_not_configured"
        assert message == "Cashier not connected"

    def test_surfaces_field_validation_detail(self) -> None:
        code, message, _ = ApiPayClient._extract_error(
            {"errors": {"phone_number": ["The phone number format is invalid."]}}, 422
        )
        assert "phone_number" in message

    def test_keeps_meta_for_rate_limits(self) -> None:
        code, _, meta = ApiPayClient._extract_error(
            {"error": "kyc_daily_limit_reached", "meta": {"reset_at": "2026-08-13T00:00:00Z"}}, 429
        )
        assert code == "kyc_daily_limit_reached"
        assert meta["reset_at"] == "2026-08-13T00:00:00Z"

    def test_survives_a_non_json_error_body(self) -> None:
        code, message, meta = ApiPayClient._extract_error(None, 502)
        assert code is None
        assert "502" in message
        assert meta == {}
