"""Regresión del fix-017: conectar Mercado Pago no puede fallar en silencio.

El problema que resuelve, en una escena: el dueño entra a Mi página, pega lo
que copió de Mercado Pago, guarda, y el panel le dice «Cuenta de Mercado Pago
conectada ✓». Se va tranquilo.

Tres días después un cliente reserva y no le aparece el botón de pagar. El
turno queda «pendiente» y nadie sabe por qué. Lo que había pegado era la
Public Key, que está justo al lado del Access Token en la misma pantalla de
Mercado Pago.

Nada en el sistema lo había mirado.
"""

import httpx
import pytest
from sqlalchemy import select

from app.models import Empresa
from app.services import empresa as svc_empresa
from app.services import mercadopago as mp

from .conftest import token_de


TOKEN_OK = "APP_USR-1234567890-valido"


class _Respuesta:
    """Una respuesta de httpx de mentira, para no salir a la red en los tests."""

    def __init__(self, status_code: int, datos: dict | None = None):
        self.status_code = status_code
        self._datos = datos or {}

    def json(self):
        return self._datos


CUENTA_MP = {
    "id": 987654321,
    "nickname": "BARBERIADONNICO",
    "email": "nico@barberia.com",
    "site_id": "MLA",
    "first_name": "Nico",
}


@pytest.fixture()
def mp_responde(monkeypatch):
    """Factory: hace que la API de MP responda lo que el test necesite."""

    def _configurar(status_code=200, datos=None, explota=False):
        llamadas = []

        def falso_get(url, **kwargs):
            llamadas.append((url, kwargs.get("headers", {})))
            if explota:
                raise httpx.ConnectError("sin red")
            return _Respuesta(status_code, datos if datos is not None else CUENTA_MP)

        monkeypatch.setattr(mp.httpx, "get", falso_get)
        return llamadas

    return _configurar


# ══════════════════════════════════════════════════════════════════════════
#  1. La validación del token
# ══════════════════════════════════════════════════════════════════════════


def test_un_token_bueno_devuelve_de_quien_es(mp_responde):
    llamadas = mp_responde()
    cuenta = mp.validar_token(TOKEN_OK)

    assert cuenta["nombre"] == "BARBERIADONNICO"
    assert cuenta["email"] == "nico@barberia.com"
    assert cuenta["pais"] == "MLA"
    # Y se preguntó con ESE token, no con otro.
    assert llamadas[0][1]["Authorization"] == f"Bearer {TOKEN_OK}"


def test_la_public_key_se_rechaza_con_un_mensaje_que_se_entiende(mp_responde):
    """EL error clásico: están una al lado de la otra en la pantalla de MP."""
    mp_responde(status_code=401)

    with pytest.raises(mp.TokenInvalido) as e:
        mp.validar_token("APP_USR-abcd-1234-efgh-5678")

    texto = str(e.value)
    assert "Public Key" in texto
    assert "Access Token" in texto


def test_el_token_de_prueba_se_rechaza_sin_salir_a_la_red(monkeypatch):
    """Con el token TEST- los pagos no son reales: el negocio no cobra nada."""

    def no_deberia_llamarse(*a, **k):
        raise AssertionError("no hay que preguntarle a MP para saber esto")

    monkeypatch.setattr(mp.httpx, "get", no_deberia_llamarse)

    with pytest.raises(mp.TokenInvalido) as e:
        mp.validar_token("TEST-1234567890-abcdef")

    assert "PRUEBA" in str(e.value)
    assert "PRODUCCIÓN" in str(e.value)


@pytest.mark.parametrize("vacio", ["", "   ", None])
def test_un_token_vacio_se_rechaza(vacio):
    with pytest.raises(mp.TokenInvalido):
        mp.validar_token(vacio)


def test_si_mercado_pago_no_contesta_lo_dice_y_no_guarda_nada(mp_responde):
    mp_responde(explota=True)
    with pytest.raises(mp.TokenInvalido) as e:
        mp.validar_token(TOKEN_OK)
    assert "comunicarme" in str(e.value)


def test_otro_error_de_mp_tambien_frena(mp_responde):
    mp_responde(status_code=500)
    with pytest.raises(mp.TokenInvalido) as e:
        mp.validar_token(TOKEN_OK)
    assert "500" in str(e.value)


def test_al_token_se_le_sacan_los_espacios(mp_responde):
    """Copiar y pegar de la pantalla de MP arrastra espacios y saltos."""
    llamadas = mp_responde()
    mp.validar_token(f"  {TOKEN_OK}\n")
    assert llamadas[0][1]["Authorization"] == f"Bearer {TOKEN_OK}"


# ══════════════════════════════════════════════════════════════════════════
#  2. Guardar desde el panel
# ══════════════════════════════════════════════════════════════════════════


def _guardar(client, ctx, token, modo="sena", monto=5000):
    return client.put(
        "/empresa/senas",
        json={
            "cobro_modo": modo,
            "sena_activa": modo != "ninguno",
            "sena_monto": monto,
            "mp_access_token": token,
        },
        headers=token_de(ctx.dueno),
    )


def test_guardar_un_token_bueno_conecta_y_muestra_la_cuenta(
    client, db, armar_empresa, mp_responde
):
    mp_responde()
    ctx = armar_empresa()

    r = _guardar(client, ctx, TOKEN_OK)

    assert r.status_code == 200
    datos = r.json()
    assert datos["mp_conectado"] is True
    assert datos["mp_cuenta"]["nombre"] == "BARBERIADONNICO"
    assert datos["mp_cuenta"]["email"] == "nico@barberia.com"


def test_guardar_un_token_malo_da_422_Y_NO_GUARDA_NADA(
    client, db, armar_empresa, mp_responde
):
    """Lo importante es el «no guarda nada»: sin esto quedaba a medias."""
    mp_responde(status_code=401)
    ctx = armar_empresa()

    r = _guardar(client, ctx, "APP_USR-esto-es-la-public-key")

    assert r.status_code == 422
    assert "Public Key" in r.json()["detail"]

    db.refresh(ctx.empresa)
    assert ctx.empresa.mp_credenciales is None
    # Y tampoco quedó a medias el resto de la config.
    assert svc_empresa.config_senas(db, ctx.empresa.id)["mp_conectado"] is False


def test_el_token_nunca_vuelve_en_la_respuesta(client, db, armar_empresa, mp_responde):
    mp_responde()
    ctx = armar_empresa()
    r = _guardar(client, ctx, TOKEN_OK)
    assert TOKEN_OK not in r.text


def test_el_token_queda_cifrado_en_la_base(client, db, armar_empresa, mp_responde):
    mp_responde()
    ctx = armar_empresa()
    _guardar(client, ctx, TOKEN_OK)

    db.refresh(ctx.empresa)
    assert TOKEN_OK.encode() not in ctx.empresa.mp_credenciales
    assert mp.token_de(ctx.empresa) == TOKEN_OK


def test_guardar_sin_token_no_pisa_el_que_ya_estaba(
    client, db, armar_empresa, mp_responde
):
    """Cambiar el monto de la seña no puede desconectar Mercado Pago."""
    mp_responde()
    ctx = armar_empresa()
    _guardar(client, ctx, TOKEN_OK)

    r = client.put(
        "/empresa/senas",
        json={"cobro_modo": "sena", "sena_activa": True, "sena_monto": 9999},
        headers=token_de(ctx.dueno),
    )

    assert r.status_code == 200
    assert r.json()["mp_conectado"] is True
    assert r.json()["sena_monto"] == 9999
    assert mp.token_de(ctx.empresa) == TOKEN_OK


def test_recepcion_no_puede_tocar_las_senas(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.get("/empresa/senas", headers=token_de(ctx.profesional))
    assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
#  3. El botón «Probar conexión»
# ══════════════════════════════════════════════════════════════════════════


def test_probar_confirma_que_sigue_andando(client, db, armar_empresa, mp_responde):
    mp_responde()
    ctx = armar_empresa()
    _guardar(client, ctx, TOKEN_OK)

    r = client.post("/empresa/senas/probar", headers=token_de(ctx.dueno))

    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["cuenta"]["nombre"] == "BARBERIADONNICO"


def test_probar_avisa_si_el_token_dejo_de_servir(
    client, db, armar_empresa, mp_responde, monkeypatch
):
    """El caso real: el dueño revoca la credencial desde Mercado Pago.

    Sin este botón, la única forma de enterarse es que un cliente no pueda
    pagar — y ese cliente no vuelve a avisar, se va.
    """
    mp_responde()
    ctx = armar_empresa()
    _guardar(client, ctx, TOKEN_OK)

    mp_responde(status_code=401)     # ahora MP lo rechaza
    r = client.post("/empresa/senas/probar", headers=token_de(ctx.dueno))

    assert r.status_code == 422
    assert "Mercado Pago rechazó" in r.json()["detail"]


def test_probar_sin_haber_conectado_lo_dice(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.post("/empresa/senas/probar", headers=token_de(ctx.dueno))
    assert r.status_code == 422
    assert "Todavía no conectaste" in r.json()["detail"]


def test_probar_actualiza_el_nombre_si_cambio(client, db, armar_empresa, mp_responde):
    mp_responde()
    ctx = armar_empresa()
    _guardar(client, ctx, TOKEN_OK)

    mp_responde(datos={**CUENTA_MP, "nickname": "NOMBRENUEVO"})
    client.post("/empresa/senas/probar", headers=token_de(ctx.dueno))

    assert svc_empresa.config_senas(db, ctx.empresa.id)["mp_cuenta"]["nombre"] == "NOMBRENUEVO"


def test_recepcion_no_puede_probar(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.post("/empresa/senas/probar", headers=token_de(ctx.profesional))
    assert r.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
#  4. Que no se haya roto lo que ya andaba
# ══════════════════════════════════════════════════════════════════════════


def test_una_empresa_sin_mp_sigue_sin_mp(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.get("/empresa/senas", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    assert r.json()["mp_conectado"] is False
    assert r.json()["mp_cuenta"] is None


def test_un_token_guardado_antes_del_fix_sigue_funcionando(db, armar_empresa):
    """Compatibilidad: los tokens viejos no traen la cuenta adentro.

    Se guardaron con el formato de antes ({"access_token": ...} y nada más).
    Tienen que seguir sirviendo para cobrar; lo único que falta es el nombre
    de la cuenta, que se completa la primera vez que se toca «Probar».
    """
    ctx = armar_empresa()
    from app.core.crypto import encriptar_credenciales

    ctx.empresa.mp_credenciales = encriptar_credenciales({"access_token": TOKEN_OK})
    db.flush()

    assert mp.token_de(ctx.empresa) == TOKEN_OK
    assert mp.cuenta_de(ctx.empresa) is None
    assert svc_empresa.config_senas(db, ctx.empresa.id)["mp_conectado"] is True


def test_dos_empresas_no_se_mezclan_las_cuentas(
    client, db, armar_empresa, mp_responde
):
    mp_responde()
    a = armar_empresa("Barbería A")
    _guardar(client, a, TOKEN_OK)

    b = armar_empresa("Barbería B")
    mp_responde(datos={**CUENTA_MP, "nickname": "OTRONEGOCIO"})
    _guardar(client, b, "APP_USR-otro-token-distinto")

    assert mp.cuenta_de(a.empresa)["nombre"] == "BARBERIADONNICO"
    assert mp.cuenta_de(b.empresa)["nombre"] == "OTRONEGOCIO"
    assert mp.token_de(a.empresa) != mp.token_de(b.empresa)


def test_el_webhook_de_mp_sigue_andando_igual(client, db, armar_empresa, monkeypatch):
    """Control: el fix no tocó el circuito de cobro."""
    from app.core.config import settings
    import app.routers.publico as publico_mod

    monkeypatch.setattr(settings, "mp_firma_modo", "off")
    ctx = armar_empresa()
    tocado = {}
    monkeypatch.setattr(
        publico_mod, "_procesar_notificacion_mp", lambda *a, **k: tocado.setdefault("si", True)
    )

    r = client.post(f"/publico/mp/webhook/{ctx.empresa.slug}?type=payment&data.id=123456789")
    assert r.status_code == 200
    assert tocado == {"si": True}


def test_crear_preferencia_sin_token_no_explota(db, armar_empresa):
    """La reserva NUNCA se cae por Mercado Pago. Sigue siendo cierto."""
    ctx = armar_empresa()
    empresa = db.scalars(select(Empresa).where(Empresa.id == ctx.empresa.id)).one()

    class _TurnoFalso:
        id = 1
        sena_monto = None

    assert mp.crear_preferencia(empresa, _TurnoFalso(), "Seña") is None
