"""Envío de emails por SMTP (Gmail con contraseña de aplicación).

Cero dependencias: smtplib + email.mime de la stdlib. Con una cuenta Gmail
normal el límite es ~500 envíos/día — de sobra para el volumen inicial.
Cuando el volumen lo pida, se cambia por un proveedor transaccional
(Resend/SendGrid) tocando solo este módulo (E7 completo).

Si faltan credenciales (SMTP_USER/SMTP_PASS), enviar() lanza
MailerNoConfigurado: quien llama decide registrar el fallo sin romper.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


class MailerNoConfigurado(Exception):
    """SMTP_USER / SMTP_PASS vacíos: no hay por dónde mandar."""


def enviar(
    destino: str,
    asunto: str,
    html: str,
    reply_to: str | None = None,
) -> None:
    """Manda un email HTML. Lanza MailerNoConfigurado o las excepciones de smtplib."""
    if not settings.smtp_user or not settings.smtp_pass:
        raise MailerNoConfigurado("SMTP sin configurar (SMTP_USER / SMTP_PASS)")

    remitente = settings.smtp_from or settings.smtp_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = f"Turnos360 <{remitente}>"
    msg["To"] = destino
    if reply_to:
        # Que el cliente responda directo al negocio, no a nuestra casilla.
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_pass)
        smtp.sendmail(remitente, [destino], msg.as_string())
