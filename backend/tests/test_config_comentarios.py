"""Un comentario como valor (`VAR=   # texto` en Docker Compose) es una variable vacía."""

from app.core.config import Settings


def test_un_comentario_como_valor_se_toma_como_vacio():
    s = Settings(
        _env_file=None,
        mp_webhook_secret="# MP → Tus integraciones → Webhooks",
        smtp_pass="# contraseña de aplicación",
        cobro_whatsapp="# formato wa.me, sin +",
        admin_alerta_email="# vacío = no se manda nada",
        sentry_dsn="# opcional",
    )
    assert s.mp_webhook_secret == ""
    assert s.smtp_pass == ""
    assert s.cobro_whatsapp == ""
    assert s.admin_alerta_email == ""
    assert s.sentry_dsn == ""


def test_un_valor_real_no_se_toca():
    s = Settings(_env_file=None, cobro_whatsapp="5492611234567", mp_webhook_secret="abc#def")
    assert s.cobro_whatsapp == "5492611234567"
    assert s.mp_webhook_secret == "abc#def"


def test_en_produccion_un_secret_key_comentario_sigue_frenando_el_arranque():
    import pytest

    with pytest.raises(ValueError, match="COMENTARIO"):
        Settings(
            _env_file=None, env="prod", secret_key="# firma de los JWT",
            fernet_key="x" * 40, cors_origins="https://turnos360.com.ar",
            public_base_url="https://turnos360.com.ar", api_base_url="https://turnos360.com.ar/api",
        )
