"""En local no hay SMTP, así que el link de verificación no existía en ningún lado.

El mail no sale, el token se guarda hasheado y la tarea de Celery terminaba
"succeeded: None" sin dejar rastro. Resultado: el alta pública no se podía
probar a mano en una máquina de desarrollo.

Estos tests cuidan las dos mitades del arreglo: que el link aparezca en el log
en dev, y que NO aparezca nunca en producción.
"""

import logging

import pytest

from app.core import mailer
from app.tasks import emails


class _FakeUsuario:
    id = 123
    nombre = "Pepe"
    email = "pepe@ejemplo.com"
    email_verificado = False
    activo = True


class _FakeDB:
    """La tarea abre su propia sesión (SessionLocal), fuera de la del test."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, modelo, pk):
        return _FakeUsuario()


@pytest.fixture()
def sin_smtp(monkeypatch):
    def explota(*a, **kw):
        raise mailer.MailerNoConfigurado("SMTP sin configurar")

    monkeypatch.setattr(emails, "SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(emails.mailer, "enviar", explota)


def _warnings(caplog):
    return [x.getMessage() for x in caplog.records if x.levelno >= logging.WARNING]


# ══════════════════════════════════════════════════════════════════════
#  En dev: el link tiene que estar
# ══════════════════════════════════════════════════════════════════════

def test_el_link_de_verificacion_queda_en_el_log(sin_smtp, monkeypatch, caplog):
    monkeypatch.setattr(emails.settings, "env", "dev")
    with caplog.at_level(logging.WARNING):
        emails.enviar_verificacion_email(123, "tok-de-prueba")

    texto = "\n".join(_warnings(caplog))
    assert "/verificar?token=tok-de-prueba" in texto, (
        "Sin SMTP el link no sale por ningún lado y el alta pública no se "
        "puede probar en local."
    )


def test_el_link_de_reseteo_queda_en_el_log(sin_smtp, monkeypatch, caplog):
    monkeypatch.setattr(emails.settings, "env", "dev")
    with caplog.at_level(logging.WARNING):
        emails.enviar_reset_password(123, "tok-de-prueba")

    assert "/restablecer?token=tok-de-prueba" in "\n".join(_warnings(caplog))


def test_sin_smtp_el_reseteo_no_reintenta(sin_smtp, monkeypatch):
    """Que falte SMTP no se arregla insistiendo: si re-lanza, Celery reintenta
    en loop y llena el log de tracebacks por un problema de configuración."""
    monkeypatch.setattr(emails.settings, "env", "dev")
    emails.enviar_reset_password(123, "tok-de-prueba")  # no tiene que explotar


# ══════════════════════════════════════════════════════════════════════
#  En producción: el link NO puede estar
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("entorno", ["prod", "produccion", "production", "PROD"])
def test_en_produccion_el_token_nunca_va_al_log(sin_smtp, monkeypatch, caplog, entorno):
    """Un token en el log es un token regalado a cualquiera que lea los logs.

    Vale incluso si alguien se olvidó de cargar SMTP en prod: el mail no sale,
    pero el link tampoco se filtra.
    """
    monkeypatch.setattr(emails.settings, "env", entorno)
    with caplog.at_level(logging.DEBUG):
        emails.enviar_verificacion_email(123, "tok-secreto")
        emails.enviar_reset_password(123, "tok-secreto")

    todo = "\n".join(x.getMessage() for x in caplog.records)
    assert "tok-secreto" not in todo, "Se filtró un token de un solo uso al log."
