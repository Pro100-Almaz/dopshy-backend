import datetime
import decimal
import typing

import fastapi
import httpx
import pytest

from src.api.routes.document import extract_document
from src.models.schemas.document import DocumentExtractIn
from src.services import document as document_module
from src.services.document import _bookings
from src.services.document import _payment_totals
from src.services.document import DocumentService


class FakeAccount:
    username = "arena-manager"
    email = "manager@example.com"


class FakeDocumentService(DocumentService):
    async def generate_document(self, payload: DocumentExtractIn, current_user: FakeAccount) -> tuple[str, bytes]:
        assert payload.bot_type == "arena"
        assert current_user.username == "arena-manager"
        return "arena-report-2026-08-01-2026-08-31.pdf", b"%PDF-1.4\n"


class FakeAsyncClient:
    request: dict[str, typing.Any] | None = None

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, typing.Any],
    ) -> httpx.Response:
        FakeAsyncClient.request = {"url": url, "headers": headers, "json": json, "timeout": self.timeout}
        return httpx.Response(
            status_code=200,
            json={
                "ok": True,
                "data": {
                    "summary": {
                        "total_paid_amount": "15000",
                        "booking_count": 1,
                        "total_booked_hours": "2",
                        "load_level": "0.027777",
                    },
                    "bookings": [
                        {
                            "customer_name": "Client One",
                            "field": 1,
                            "date": "2026-08-01",
                            "time_start": "10:00",
                            "time_end": "12:00",
                            "price_total": "15000",
                            "paid_cash": "5000",
                            "paid_kaspi_qr": "5000",
                            "paid_api": "4000",
                            "paid_avans": "1000",
                            "state": "confirmed",
                        }
                    ],
                },
            },
        )


@pytest.mark.asyncio
async def test_extract_document_returns_pdf_response() -> None:
    payload = DocumentExtractIn(bot_type="arena", start_date="2026-08-01", end_date="2026-08-31")

    response = await extract_document(
        payload=payload,
        current_user=FakeAccount(),
        document_service=FakeDocumentService(),
    )

    assert response.status_code == fastapi.status.HTTP_200_OK
    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF")
    assert response.headers["content-disposition"] == ('attachment; filename="arena-report-2026-08-01-2026-08-31.pdf"')


@pytest.mark.asyncio
async def test_document_service_rejects_non_arena_reports() -> None:
    payload = DocumentExtractIn(bot_type="box_academy", start_date="2026-08-01", end_date="2026-08-31")

    with pytest.raises(fastapi.HTTPException) as exc_info:
        await DocumentService().generate_document(payload=payload, current_user=FakeAccount())

    assert exc_info.value.status_code == fastapi.status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == "Only arena document extraction is supported now."


@pytest.mark.asyncio
async def test_document_service_posts_extract_data_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MANAGER_API_KEY", "manager-token")
    monkeypatch.setattr(document_module.settings, "BOT_URL", "http://bot.local")
    monkeypatch.setattr(document_module.httpx, "AsyncClient", FakeAsyncClient)
    payload = DocumentExtractIn(bot_type="arena", start_date="2026-08-01", end_date="2026-08-31")

    filename, pdf = await DocumentService().generate_document(payload=payload, current_user=FakeAccount())

    assert filename == "arena-report-2026-08-01-2026-08-31.pdf"
    assert pdf.startswith(b"%PDF")
    assert FakeAsyncClient.request == {
        "url": "http://bot.local/api/manager/documents/extract-data",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": "manager-token",
            "Authorization": "Bearer manager-token",
        },
        "json": {
            "bot_type": "arena",
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
        },
        "timeout": 30.0,
    }


def test_document_extract_in_validates_date_order() -> None:
    with pytest.raises(ValueError):
        DocumentExtractIn(bot_type="arena", start_date="2026-08-31", end_date="2026-08-01")


def test_document_service_renders_bot_success_payload() -> None:
    payload = DocumentExtractIn(bot_type="arena", start_date="2026-08-01", end_date="2026-08-31")
    report_data = {
        "ok": True,
        "data": {
            "bot_type": "arena",
            "bot": "Arena",
            "period": {"start_date": "2026-08-01", "end_date": "2026-08-31", "days": 31},
            "included_statuses": ["completed", "confirmed"],
            "active_field_count": 3,
            "generated_at": "2026-08-26T12:30:00+05:00",
            "summary": {
                "total_paid_amount": 47000,
                "booking_count": 2,
                "total_booked_hours": 3,
                "load_level": 0.0013,
                "load_level_percent": 0.13,
                "per_field_load": [
                    {
                        "field": 1,
                        "booked_hours": 2,
                        "load_level": 0.0027,
                        "load_level_percent": 0.27,
                    }
                ],
            },
            "bookings": [
                {
                    "id": 1,
                    "customer_name": "Aruzhan",
                    "field": 1,
                    "date": "2026-08-03",
                    "time_start": "10:00",
                    "time_end": "12:00",
                    "duration_hours": 2,
                    "price_total": 40000,
                    "paid_cash": 10000,
                    "paid_kaspi_qr": 0,
                    "paid_api": 25000,
                    "paid_avans": 5000,
                    "total_paid_amount": 40000,
                    "state": "confirmed",
                    "source": "manager",
                }
            ],
        },
    }

    pdf = DocumentService()._render_arena_pdf(
        report_data=report_data,
        payload=payload,
        current_user=FakeAccount(),
    )

    assert pdf.startswith(b"%PDF")


def test_document_service_falls_back_when_reportlab_rendering_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = DocumentExtractIn(bot_type="arena", start_date="2026-08-01", end_date="2026-08-31")

    def raise_render_error(*args: object, **kwargs: object) -> bytes:
        raise ValueError("layout failed")

    monkeypatch.setattr(document_module, "_render_reportlab_pdf", raise_render_error)

    pdf = DocumentService()._render_arena_pdf(
        report_data={"data": {"bookings": []}},
        payload=payload,
        current_user=FakeAccount(),
    )

    assert pdf.startswith(b"%PDF")


def test_bookings_keeps_only_confirmed_and_completed_rows() -> None:
    rows = _bookings(
        {
            "bookings": [
                {"id": 1, "state": "confirmed"},
                {"id": 2, "status": "completed"},
                {"id": 3, "state": "cancelled"},
                {"id": 4, "status": "pending"},
            ]
        }
    )

    assert [row["id"] for row in rows] == [1, 2]


def test_payment_totals_sum_supported_payment_aliases() -> None:
    totals = _payment_totals(
        [
            {
                "paid_cash": "10000",
                "paid_kaspi_qr": 5000,
                "paid_api": "25000.50",
                "paid_avans": "",
            },
            {
                "paid_cash": None,
                "paid_qr": "7000",
                "remote_payment": 3000,
                "prepayment": "2000",
            },
        ]
    )

    assert totals == {
        "cash": decimal.Decimal("10000"),
        "qr": decimal.Decimal("12000"),
        "remote": decimal.Decimal("28000.50"),
        "prepayment": decimal.Decimal("2000"),
    }
