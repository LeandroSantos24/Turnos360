"""Regresión del fix-019: un .env mal escrito no puede pasar desapercibido.

Tres variables de texto libre gobiernan cosas que, escritas mal, se rompían
en silencio. No fallaban: hacían otra cosa.

    WA_PROVEEDOR=Simulado   (S mayúscula)  -> los mensajes SALÍAN
    MP_FIRMA_MODO=enforced  (con d)        -> validaba pero no bloqueaba
    ENV=prd                                -> se apagaban los fail-fast de
                                              producción y el candado del seed

El peor de los tres es el primero, porque el error apunta al lado peligroso:
un typo en el freno de mano lo soltaba.
"""

import pytest
from pydantic import ValidationError

from app.core.config import ENTORNOS, MP_FIRMA_MODOS, WA_PROVEEDORES, Settings


def _settings(**kw) -> Settings:
    """Settings sin leer el .env del disco: solo lo que le pasamos."""
    return Settings(_env_file=None, **kw)


# ══════════════════════════════════════════════════════════════════════════
#  1. Los defaults son válidos (si no, no arrancaría nada)
# ══════════════════════════════════════════════════════════════════════════


def test_los_valores_por_defecto_son_validos():
    s = _settings()
    assert s.wa_proveedor in WA_PROVEEDORES
    assert s.mp_firma_modo in MP_FIRMA_MODOS
    assert s.env in ENTORNOS


def test_el_default_de_whatsapp_es_el_freno_puesto():
    """Que el sistema nazca sin mandar mensajes no es un detalle: es la
    diferencia entre una prueba y un mensaje a un teléfono real."""
    assert _settings().wa_proveedor == "simulado"


def test_el_default_de_la_firma_de_mp_no_bloquea_nada():
    """`off` se comporta igual que antes de que esto existiera. Subir un
    escalón tiene que ser una decisión, no un efecto secundario."""
    assert _settings().mp_firma_modo == "off"


# ══════════════════════════════════════════════════════════════════════════
#  2. Lo que no existe frena el arranque
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "valor",
    [
        "simulad",
        "simulacion",
        "meta-cloud",
        "Meta Cloud",
        "true",
        "si",
        "",
        "   ",
    ],
)
def test_un_proveedor_de_whatsapp_que_no_existe_frena_el_arranque(valor):
    with pytest.raises(ValidationError, match="WA_PROVEEDOR"):
        _settings(wa_proveedor=valor)


@pytest.mark.parametrize(
    "valor", ["enforced", "enforcing", "on", "true", "logs", "bloquear", "", "  "]
)
def test_un_modo_de_firma_que_no_existe_frena_el_arranque(valor):
    with pytest.raises(ValidationError, match="MP_FIRMA_MODO"):
        _settings(mp_firma_modo=valor)


@pytest.mark.parametrize("valor", ["prd", "produccón", "pro", "productivo", "", " "])
def test_un_entorno_que_no_existe_frena_el_arranque(valor):
    with pytest.raises(ValidationError, match="ENV"):
        _settings(env=valor)


def test_el_error_dice_cuales_son_los_valores_validos():
    """Un error que no dice qué poner obliga a leer el código fuente."""
    with pytest.raises(ValidationError) as e:
        _settings(mp_firma_modo="enforced")
    texto = str(e.value)
    assert "off" in texto and "log" in texto and "enforce" in texto


# ══════════════════════════════════════════════════════════════════════════
#  3. Lo que es una intención clara se perdona
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "escrito,esperado",
    [
        ("simulado", "simulado"),
        ("Simulado", "simulado"),
        ("SIMULADO", "simulado"),
        ("  simulado  ", "simulado"),
        ("Meta", "meta"),
        ("META", "meta"),
    ],
)
def test_mayusculas_y_espacios_no_son_un_error(escrito, esperado):
    """`WA_PROVEEDOR=Simulado ` es una intención clarísima. Rechazarla sería
    pedantería; lo que hay que rechazar es lo que no existe."""
    assert _settings(wa_proveedor=escrito).wa_proveedor == esperado


@pytest.mark.parametrize("escrito", ["Enforce", "ENFORCE", " enforce "])
def test_el_modo_de_firma_tambien_se_normaliza(escrito):
    assert _settings(mp_firma_modo=escrito).mp_firma_modo == "enforce"


@pytest.mark.parametrize("escrito", ["PROD", " Prod ", "Production", "PRODUCCION"])
def test_el_entorno_se_normaliza_y_sigue_siendo_produccion(escrito):
    """Lo importante no es el string sino que `es_produccion` siga dando True:
    de esa propiedad cuelgan los fail-fast y el candado del seed."""
    s = _settings(
        env=escrito,
        secret_key="una-clave-larga-de-verdad-para-produccion",
        fernet_key="otra-clave-distinta-y-tambien-larga",
    )
    assert s.es_produccion is True


# ══════════════════════════════════════════════════════════════════════════
#  4. Los fail-fast de producción siguen andando
# ══════════════════════════════════════════════════════════════════════════


def test_en_produccion_sigue_exigiendo_los_secretos():
    """El validador nuevo corre ANTES que este. Si se hubiera comido la
    excepción, producción arrancaría con la clave de relleno."""
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(env="prod")


def test_un_entorno_mal_escrito_ya_no_saltea_los_fail_fast():
    """El agujero original: ENV=prd no era producción para nadie, así que
    SECRET_KEY sin configurar pasaba sin decir nada."""
    with pytest.raises(ValidationError, match="ENV"):
        _settings(env="prd")


def test_en_desarrollo_no_exige_nada():
    s = _settings(env="dev")
    assert s.es_produccion is False
