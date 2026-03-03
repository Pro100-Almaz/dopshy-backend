import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config.manager import settings


async def send_verification_email(recipient_email: str, code: str) -> None:
    await asyncio.to_thread(_send_email_sync, recipient_email, code)


def _send_email_sync(recipient_email: str, code: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Код подтверждения Dopshy"
    msg["From"] = settings.SMTP_SENDER_EMAIL
    msg["To"] = recipient_email

    body = (
        f"Ваш код подтверждения: {code}\n"
        "Код действителен в течение 10 минут.\n"
        "Если вы не регистрировались — проигнорируйте это письмо."
    )
    html_body = (
        f"<p>Ваш код подтверждения: <strong>{code}</strong></p>"
        "<p>Код действителен в течение 10 минут.</p>"
        "<p>Если вы не регистрировались — проигнорируйте это письмо.</p>"
    )

    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_SENDER_EMAIL, recipient_email, msg.as_string())
