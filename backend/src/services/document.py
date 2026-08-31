import datetime
import decimal
import html
import io
import os
import pathlib
import typing

import fastapi
import httpx

from src.config.manager import settings
from src.models.db.account import Account
from src.models.schemas.document import DocumentBotType, DocumentExtractIn

REPORT_INCLUDED_STATUSES = {"confirmed", "completed"}


class DocumentService:
    async def generate_document(self, payload: DocumentExtractIn, current_user: Account) -> tuple[str, bytes]:
        if payload.bot_type != DocumentBotType.ARENA:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_400_BAD_REQUEST,
                detail="Only arena document extraction is supported now.",
            )

        report_data = await self._fetch_report_data(payload=payload)
        filename = f"arena-report-{payload.start_date.isoformat()}-" f"{payload.end_date.isoformat()}.pdf"
        return filename, self._render_arena_pdf(
            report_data=report_data,
            payload=payload,
            current_user=current_user,
        )

    async def _fetch_report_data(self, payload: DocumentExtractIn) -> dict[str, typing.Any]:
        base_url = settings.BOT_URL
        if not base_url:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="BOT_URL is not configured.",
            )

        url = base_url.rstrip("/") + "/api/manager/documents/extract-data"
        manager_api_key = os.getenv("MANAGER_API_KEY") or settings.MANAGER_API_KEY or ""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": manager_api_key,
        }
        if manager_api_key:
            headers["Authorization"] = f"Bearer {manager_api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload.model_dump(mode="json"),
                )
            except httpx.HTTPError as exc:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to reach the bot document service.",
                ) from exc

        if response.status_code >= 400:
            detail = self._bot_error_detail(response)
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail=detail,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot document service returned a non-JSON response.",
            ) from exc

        if not isinstance(data, dict):
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
                detail="Bot document service returned an invalid report payload.",
            )
        return data

    def _bot_error_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"Bot document service returned {response.status_code}: {response.text[:200]}"

        if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
            return payload["detail"]
        return f"Bot document service returned {response.status_code}: {response.text[:200]}"

    def _render_arena_pdf(
        self,
        *,
        report_data: dict[str, typing.Any],
        payload: DocumentExtractIn,
        current_user: Account,
    ) -> bytes:
        data = _unwrap_report_data(report_data)
        lines = _arena_report_lines(
            data=data,
            payload=payload,
            generated_by=_account_label(current_user),
        )

        try:
            return _render_reportlab_pdf(lines=lines, data=data)
        except Exception:
            return _render_basic_pdf(lines)


def _unwrap_report_data(report_data: dict[str, typing.Any]) -> dict[str, typing.Any]:
    data = report_data.get("data")
    return data if isinstance(data, dict) else report_data


def _account_label(account: Account) -> str:
    username = getattr(account, "username", None)
    email = getattr(account, "email", None)
    return str(username or email or "unknown")


def _arena_report_lines(
    *,
    data: dict[str, typing.Any],
    payload: DocumentExtractIn,
    generated_by: str,
) -> list[str]:
    summary = _summary(data)
    bookings = _bookings(data)
    period = _period(data, payload)
    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "Отчет Dopshy Арена",
        "Бот: Арена",
        f"Период: {period['start_date']} - {period['end_date']}",
        f"Сформировано: {generated_at}",
        f"Сформировал: {generated_by}",
        "",
        "Сводка",
        f"Общая сумма оплат: {_money_kzt(summary.get('total_paid_amount'))}",
        f"Количество броней: {summary.get('booking_count', len(bookings))}",
        f"Забронированные часы: {_number(summary.get('total_booked_hours'))}",
    ]

    payment_totals = _payment_totals(bookings)
    lines.extend(
        [
            "",
            "Итоги оплат",
            f"Наличные: {_money_kzt(payment_totals['cash'])}",
            f"QR: {_money_kzt(payment_totals['qr'])}",
            f"Онлайн: {_money_kzt(payment_totals['remote'])}",
            f"Предоплата: {_money_kzt(payment_totals['prepayment'])}",
        ]
    )

    lines.append("")
    lines.append("Бронирования")
    if not bookings:
        lines.append("За выбранный период нет подтвержденных или завершенных броней.")
        return lines

    header = "Клиент | Поле | Дата | Начало | Конец | Часы | Цена | Наличные | QR | " "Онлайн | Предоплата | Статус"
    lines.append(header)
    lines.append("-" * len(header))
    for booking in bookings:
        lines.append(
            " | ".join(
                [
                    _text(_pick(booking, "client_name", "customer_name", "guest_name")),
                    _text(_pick(booking, "field_name", "field")),
                    _text(_pick(booking, "booking_date", "date")),
                    _text(_pick(booking, "time_start", "start_time")),
                    _text(_pick(booking, "time_end", "end_time")),
                    _duration(booking),
                    _money(_pick(booking, "price", "price_total", "total_price")),
                    _money(booking.get("paid_cash")),
                    _money(_pick(booking, "paid_qr", "paid_kaspi_qr")),
                    _money(_pick(booking, "remote_payment", "paid_api")),
                    _money(_pick(booking, "prepayment", "paid_avans")),
                    _text(_pick(booking, "status", "state")),
                ]
            )
        )
    return lines


def _render_reportlab_pdf(*, lines: list[str], data: dict[str, typing.Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    green = colors.HexColor("#16A34A")
    green_light = colors.HexColor("#F0FDF4")
    text_primary = colors.HexColor("#111827")
    border = colors.HexColor("#E5E7EB")
    section_bg = colors.HexColor("#F9FAFB")
    header_text = colors.HexColor("#374151")
    warning = colors.HexColor("#D97706")
    error = colors.HexColor("#DC2626")

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.85 * cm,
        rightMargin=0.85 * cm,
        topMargin=0.85 * cm,
        bottomMargin=0.85 * cm,
    )
    styles = getSampleStyleSheet()
    font_name = _reportlab_font_name(pdfmetrics=pdfmetrics, TTFont=TTFont)
    for style_name in ("Normal", "Heading3", "Title", "BodyText"):
        styles[style_name].fontName = font_name
    title_style = styles["Title"].clone("ReportTitle")
    title_style.fontName = font_name
    title_style.fontSize = 20
    title_style.leading = 24
    title_style.textColor = text_primary
    title_style.alignment = 0

    body_style = styles["BodyText"].clone("ReportBody")
    body_style.fontName = font_name
    body_style.fontSize = 8
    body_style.leading = 10
    body_style.textColor = text_primary

    meta_value_style = body_style.clone("MetaValue")
    meta_value_style.fontSize = 9
    meta_value_style.leading = 11
    meta_value_style.textColor = text_primary

    section_style = styles["Heading3"].clone("SectionHeading")
    section_style.fontName = font_name
    section_style.fontSize = 12
    section_style.leading = 15
    section_style.textColor = text_primary

    table_header_style = body_style.clone("TableHeader")
    table_header_style.fontSize = 7.5
    table_header_style.leading = 9
    table_header_style.textColor = header_text

    cell_style = body_style.clone("TableCell")
    cell_style.fontSize = 7.5
    cell_style.leading = 9

    cell_right_style = cell_style.clone("TableCellRight")
    cell_right_style.alignment = 2

    cell_center_style = cell_style.clone("TableCellCenter")
    cell_center_style.alignment = 1

    story: list[typing.Any] = []
    summary = _summary(data)
    bookings = _bookings(data)
    period = _report_period(data=data, lines=lines)
    generated_at = _report_generated_at(data=data, lines=lines)
    generated_by = _line_value(lines, "Сформировал") or "неизвестно"
    page_width = landscape(A4)[0] - document.leftMargin - document.rightMargin

    header = Table(
        [
            [
                Paragraph("<b>Отчет Dopshy Арена</b>", title_style),
                Paragraph(
                    f"<font color='#6B7280'>Сформировано:</font> {html.escape(generated_at)}<br/>"
                    f"<font color='#6B7280'>Сформировал:</font> {html.escape(generated_by)}",
                    body_style,
                ),
            ],
            ["", ""],
        ],
        colWidths=[page_width * 0.62, page_width * 0.38],
        rowHeights=[34, 4],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, border),
                ("BACKGROUND", (0, 1), (0, 1), green),
                ("LINEBELOW", (0, 1), (-1, 1), 0.3, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 8))

    meta_items = [
        ("Бот", _bot_label(data.get("bot") or "arena")),
        ("Период", f"{_text(period.get('start_date'))} - {_text(period.get('end_date'))}"),
        ("Дней", _number(period.get("days")) if period.get("days") not in (None, "") else "-"),
    ]
    meta_table = Table(
        [[_metric_cell(label, value, meta_value_style) for label, value in meta_items]],
        colWidths=[page_width / len(meta_items)] * len(meta_items),
    )
    meta_table.setStyle(_section_table_style(border=border, background=section_bg))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    kpis = [
        ("Общая сумма оплат", _money_kzt(summary.get("total_paid_amount")), green),
        ("Количество броней", str(summary.get("booking_count", len(bookings))), text_primary),
        ("Забронированные часы", _number(summary.get("total_booked_hours")), text_primary),
    ]
    kpi_table = Table(
        [
            [
                _metric_cell(label, value, _kpi_value_style(body_style, color)) for label, value, color in kpis
            ]
        ],
        colWidths=[page_width / len(kpis)] * len(kpis),
    )
    kpi_table.setStyle(_section_table_style(border=border, background=colors.white))
    story.append(kpi_table)

    payment_totals = _payment_totals(bookings)
    payment_items = [
        ("Наличные", _money_kzt(payment_totals["cash"])),
        ("QR", _money_kzt(payment_totals["qr"])),
        ("Онлайн", _money_kzt(payment_totals["remote"])),
        ("Предоплата", _money_kzt(payment_totals["prepayment"])),
    ]
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Итоги оплат</b>", section_style))
    payment_table = Table(
        [[_metric_cell(label, value, meta_value_style) for label, value in payment_items]],
        colWidths=[page_width / len(payment_items)] * len(payment_items),
    )
    payment_table.setStyle(_section_table_style(border=border, background=section_bg))
    story.append(payment_table)

    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Бронирования</b>", section_style))
    if not bookings:
        empty = Table([[Paragraph("За выбранный период нет подтвержденных или завершенных броней.", body_style)]])
        empty.setStyle(_section_table_style(border=border, background=section_bg))
        story.append(empty)
    else:
        table_data = [
            [
                Paragraph(f"<b>{label}</b>", table_header_style)
                for label in (
                    "Клиент",
                    "Поле",
                    "Дата",
                    "Начало",
                    "Конец",
                    "Часы",
                    "Цена",
                    "Наличные",
                    "QR",
                    "Онлайн",
                    "Предоплата",
                    "Статус",
                )
            ]
        ]
        for booking in bookings:
            status_value = _pick(booking, "status", "state")
            status = _status_label(status_value)
            status_color = _status_color(status_value)
            table_data.append(
                [
                    Paragraph(
                        html.escape(
                            _truncate(_text(_pick(booking, "client_name", "customer_name", "guest_name")), 28)
                        ),
                        cell_style,
                    ),
                    Paragraph(html.escape(_truncate(_text(_pick(booking, "field_name", "field")), 16)), cell_style),
                    Paragraph(html.escape(_text(_pick(booking, "booking_date", "date"))), cell_center_style),
                    Paragraph(html.escape(_text(_pick(booking, "time_start", "start_time"))), cell_center_style),
                    Paragraph(html.escape(_text(_pick(booking, "time_end", "end_time"))), cell_center_style),
                    Paragraph(_duration(booking), cell_right_style),
                    Paragraph(_money_kzt(_pick(booking, "price", "price_total", "total_price")), cell_right_style),
                    Paragraph(_money_kzt(booking.get("paid_cash")), cell_right_style),
                    Paragraph(_money_kzt(_pick(booking, "paid_qr", "paid_kaspi_qr")), cell_right_style),
                    Paragraph(_money_kzt(_pick(booking, "remote_payment", "paid_api")), cell_right_style),
                    Paragraph(_money_kzt(_pick(booking, "prepayment", "paid_avans")), cell_right_style),
                    Paragraph(f"<font color='{status_color}'><b>{html.escape(status)}</b></font>", cell_style),
                ]
            )
        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[
                38 * mm,
                18 * mm,
                22 * mm,
                15 * mm,
                15 * mm,
                16 * mm,
                23 * mm,
                22 * mm,
                22 * mm,
                24 * mm,
                23 * mm,
                24 * mm,
            ],
        )
        table_style = _data_table_style(border=border, header_bg=section_bg, zebra_bg=section_bg)
        for row_index, booking in enumerate(bookings, start=1):
            status = str(_pick(booking, "status", "state") or "").lower()
            if status in REPORT_INCLUDED_STATUSES:
                table_style.add("TEXTCOLOR", (-1, row_index), (-1, row_index), green)
                table_style.add("BACKGROUND", (-1, row_index), (-1, row_index), green_light)
            elif status in {"pending", "new"}:
                table_style.add("TEXTCOLOR", (-1, row_index), (-1, row_index), warning)
            elif status in {"cancelled", "canceled"}:
                table_style.add("TEXTCOLOR", (-1, row_index), (-1, row_index), error)
        table.setStyle(table_style)
        story.append(table)

    document.build(story)
    return buffer.getvalue()


def _metric_cell(label: str, value: str, value_style: typing.Any) -> typing.Any:
    from reportlab.platypus import Paragraph

    return Paragraph(
        f"<font color='#9CA3AF' size='7'>{html.escape(label)}</font><br/><b>{html.escape(value)}</b>",
        value_style,
    )


def _report_period(*, data: dict[str, typing.Any], lines: list[str]) -> dict[str, typing.Any]:
    value = data.get("period")
    if isinstance(value, dict):
        return value
    period_text = _line_value(lines, "Период")
    if period_text and " - " in period_text:
        start_date, end_date = period_text.split(" - ", 1)
        return {"start_date": start_date, "end_date": end_date}
    return {}


def _kpi_value_style(base_style: typing.Any, color: typing.Any) -> typing.Any:
    style = base_style.clone(f"KpiValue{str(color)}")
    style.fontSize = 14
    style.leading = 17
    style.textColor = color
    return style


def _section_table_style(*, border: typing.Any, background: typing.Any) -> typing.Any:
    from reportlab.platypus import TableStyle

    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("BOX", (0, 0), (-1, -1), 0.5, border),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, border),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]
    )


def _data_table_style(*, border: typing.Any, header_bg: typing.Any, zebra_bg: typing.Any) -> typing.Any:
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle

    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#374151")),
            ("BOX", (0, 0), (-1, -1), 0.5, border),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, border),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, zebra_bg]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def _report_generated_at(*, data: dict[str, typing.Any], lines: list[str]) -> str:
    value = data.get("generated_at")
    if isinstance(value, str) and value:
        try:
            parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if parsed.tzinfo is None:
            return parsed.strftime("%Y-%m-%d %H:%M")
        if parsed.utcoffset() == datetime.timedelta(0):
            return parsed.strftime("%Y-%m-%d %H:%M UTC")
        return parsed.strftime("%Y-%m-%d %H:%M %z")
    return _line_value(lines, "Сформировано") or datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )


def _line_value(lines: list[str], label: str) -> str | None:
    prefix = f"{label}: "
    for line in lines:
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    return None


def _money_kzt(value: typing.Any) -> str:
    number = _decimal(value)
    if number == number.to_integral():
        amount = f"{int(number):,}"
    else:
        amount = f"{number:,.2f}"
    return f"{amount} ₸"


def _status_label(value: typing.Any) -> str:
    text = _text(value)
    if text == "-":
        return text
    labels = {
        "confirmed": "Подтверждено",
        "completed": "Завершено",
        "pending": "В ожидании",
        "new": "Новая",
        "cancelled": "Отменено",
        "canceled": "Отменено",
    }
    return labels.get(text.lower(), text.replace("_", " ").title())


def _bot_label(value: typing.Any) -> str:
    text = _text(value)
    if text.lower() == "arena":
        return "Арена"
    return text


def _status_color(value: typing.Any) -> str:
    status = str(value or "").lower()
    if status in REPORT_INCLUDED_STATUSES:
        return "#16A34A"
    if status in {"pending", "new"}:
        return "#D97706"
    if status in {"cancelled", "canceled"}:
        return "#DC2626"
    return "#6B7280"


def _payment_totals(bookings: list[dict[str, typing.Any]]) -> dict[str, decimal.Decimal]:
    totals = {
        "cash": decimal.Decimal("0"),
        "qr": decimal.Decimal("0"),
        "remote": decimal.Decimal("0"),
        "prepayment": decimal.Decimal("0"),
    }
    for booking in bookings:
        totals["cash"] += _decimal(booking.get("paid_cash"))
        totals["qr"] += _decimal(_pick(booking, "paid_qr", "paid_kaspi_qr"))
        totals["remote"] += _decimal(_pick(booking, "remote_payment", "paid_api"))
        totals["prepayment"] += _decimal(_pick(booking, "prepayment", "paid_avans"))
    return totals


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max(0, max_length - 3)].rstrip() + "..."


def _reportlab_font_name(*, pdfmetrics: typing.Any, TTFont: typing.Any) -> str:
    font_path = pathlib.Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font_path.exists():
        return "Helvetica"
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(font_path)))
    return "DejaVuSans"


def _render_basic_pdf(lines: list[str]) -> bytes:
    pages = [lines[i : i + 42] for i in range(0, len(lines), 42)] or [[]]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    page_ids: list[int] = []
    for page_lines in pages:
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        content = _basic_pdf_content(page_lines)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream"
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n" f"startxref\n{xref_start}\n%%EOF\n").encode("ascii")
    )
    return bytes(output)


def _basic_pdf_content(lines: list[str]) -> bytes:
    parts = ["BT", "/F1 10 Tf", "40 555 Td", "14 TL"]
    for line in lines:
        parts.append(f"({_pdf_escape(line)}) Tj")
        parts.append("T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", errors="replace")


def _pdf_escape(value: str) -> str:
    return (
        value.encode("latin-1", errors="replace")
        .decode("latin-1")
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _summary(data: dict[str, typing.Any]) -> dict[str, typing.Any]:
    value = data.get("summary") or data.get("totals") or {}
    return value if isinstance(value, dict) else {}


def _bookings(data: dict[str, typing.Any]) -> list[dict[str, typing.Any]]:
    value = data.get("bookings") or data.get("rows") or []
    return [item for item in value if isinstance(item, dict) and _is_report_booking(item)]


def _is_report_booking(booking: dict[str, typing.Any]) -> bool:
    status = _pick(booking, "status", "state")
    return status is None or str(status).lower() in REPORT_INCLUDED_STATUSES


def _period(data: dict[str, typing.Any], payload: DocumentExtractIn) -> dict[str, str]:
    value = data.get("period")
    if isinstance(value, dict):
        return {
            "start_date": str(value.get("start_date") or payload.start_date.isoformat()),
            "end_date": str(value.get("end_date") or payload.end_date.isoformat()),
        }
    return {"start_date": payload.start_date.isoformat(), "end_date": payload.end_date.isoformat()}


def _pick(source: dict[str, typing.Any], *keys: str) -> typing.Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def _duration(booking: dict[str, typing.Any]) -> str:
    explicit = _pick(booking, "duration_hours", "booked_hours", "hours")
    if explicit not in (None, ""):
        return _number(explicit)
    start = _parse_time(_pick(booking, "time_start", "start_time"))
    end = _parse_time(_pick(booking, "time_end", "end_time"))
    if start is None or end is None:
        return "0"
    start_minutes = start.hour * 60 + start.minute
    end_value = str(_pick(booking, "time_end", "end_time"))
    if end == datetime.time(0, 0) and end_value == "24:00":
        end_minutes = 24 * 60
    else:
        end_minutes = end.hour * 60 + end.minute
    return _number(decimal.Decimal(max(0, end_minutes - start_minutes)) / decimal.Decimal(60))


def _parse_time(value: typing.Any) -> datetime.time | None:
    if isinstance(value, datetime.time):
        return value
    if not isinstance(value, str):
        return None
    if value == "24:00":
        return datetime.time(0, 0)
    try:
        return datetime.time.fromisoformat(value)
    except ValueError:
        return None


def _money(value: typing.Any) -> str:
    return f"{_decimal(value):,.2f}"


def _number(value: typing.Any) -> str:
    number = _decimal(value)
    if number == number.to_integral():
        return f"{int(number)}"
    return f"{number.normalize():f}"


def _decimal(value: typing.Any) -> decimal.Decimal:
    if value in (None, ""):
        return decimal.Decimal("0")
    try:
        return decimal.Decimal(str(value))
    except decimal.InvalidOperation:
        return decimal.Decimal("0")


def _text(value: typing.Any) -> str:
    return "-" if value in (None, "") else str(value)
