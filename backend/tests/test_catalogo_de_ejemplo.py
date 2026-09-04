"""«Ya tenía unos servicios precargados, eso está mal.»

Lo dijo Leandro probando el alta como un cliente real, y tenía razón a medias.

Cargar los servicios típicos del rubro está BIEN: una pantalla en blanco el
primer día es peor que unos ejemplos. Lo que estaba mal es que nadie avisara
que son ejemplos. Aparecen como si fueran suyos, con precios que no son los
suyos, y el primer turno se puede cobrar mal sin que nadie note por qué.

POR QUÉ SE COMPARA CONTRA EL PRESET Y NO SE GUARDA UNA MARCA
Una columna «es_de_ejemplo» habría que apagarla al editar, al cambiar el
precio, al renombrar. El día que un camino se olvide de apagarla, el cartel le
dice «esto es de ejemplo» a alguien que lleva medio año trabajando con ese
servicio. La comparación no se puede desincronizar.
"""

from sqlalchemy import select

from app.models.agenda import Servicio
from app.services import catalogo_inicial as cat


PRESET = {
    "servicios": [
        {"nombre": "Corte de pelo", "duracion_min": 30, "precio": 8000},
        {"nombre": "Barba", "duracion_min": 20, "precio": 5000},
    ]
}


def _vaciar(db, ctx):
    """Deja la empresa sin catálogo ACTIVO.

    Se desactivan en vez de borrarse: el servicio del fixture ya está atado a
    un recurso y borrarlo viola la FK de servicio_recurso. La función bajo
    prueba solo mira los activos, que es lo que la pantalla muestra.
    """
    for s in db.scalars(
        select(Servicio).where(Servicio.empresa_id == ctx.empresa.id)
    ).all():
        s.activo = False
    db.flush()


def _con_preset(db, ctx):
    """Empresa con un preset propio y su catálogo de fábrica ya cargado.

    El preset se pone en `config_pack` —que pisa al del rubro, igual que en
    producción— en vez de depender del rubro del fixture: ese rubro no define
    servicios, así que apoyarse en él hacía que los tests pasaran sin ejecutar
    la lógica. Se detectó probando que `sembrar` devolvía cero.
    """
    _vaciar(db, ctx)
    ctx.empresa.config_pack = PRESET
    db.flush()
    for p in PRESET["servicios"]:
        _servicio(db, ctx, p["nombre"])
    return PRESET["servicios"]


def _servicio(db, ctx, nombre):
    s = Servicio(
        empresa_id=ctx.empresa.id, nombre=nombre, duracion_min=30, activo=True
    )
    db.add(s)
    db.flush()
    return s


def test_el_catalogo_recien_sembrado_es_de_ejemplo(db, armar_empresa):
    ctx = armar_empresa()
    _con_preset(db, ctx)
    assert cat.sigue_siendo_el_de_ejemplo(db, ctx.empresa.id) is True


def test_crear_uno_propio_apaga_el_aviso(db, armar_empresa):
    """Quien ya empezó a armar su catálogo no necesita que le expliquen de
    dónde salieron los otros."""
    ctx = armar_empresa()
    _con_preset(db, ctx)
    _servicio(db, ctx, "Un servicio mío que no está en ningún preset")
    assert cat.sigue_siendo_el_de_ejemplo(db, ctx.empresa.id) is False


def test_renombrar_uno_apaga_el_aviso(db, armar_empresa):
    """Renombrar es la señal más clara de que lo está haciendo suyo."""
    ctx = armar_empresa()
    _con_preset(db, ctx)
    uno = db.scalars(
        select(Servicio).where(
            Servicio.empresa_id == ctx.empresa.id, Servicio.activo.is_(True)
        )
    ).first()
    uno.nombre = "Corte como lo llamo yo"
    db.flush()
    assert cat.sigue_siendo_el_de_ejemplo(db, ctx.empresa.id) is False


def test_sin_servicios_no_hay_aviso(db, armar_empresa):
    """Un catálogo vacío no es «de ejemplo»: no hay nada que aclarar, y el
    cartel encima de una pantalla vacía solo agrega ruido."""
    ctx = armar_empresa()
    ctx.empresa.config_pack = PRESET
    _vaciar(db, ctx)
    assert cat.sigue_siendo_el_de_ejemplo(db, ctx.empresa.id) is False


def test_el_endpoint_contesta_al_dueno(client, db, armar_empresa):
    from .conftest import token_de

    ctx = armar_empresa()
    db.commit()
    r = client.get("/servicios/son-de-ejemplo", headers=token_de(ctx.dueno))
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["de_ejemplo"], bool)


def test_la_ruta_no_la_come_el_parametro_id(client, db, armar_empresa):
    """«son-de-ejemplo» va declarada ANTES de /{servicio_id}. Si estuviera
    después, FastAPI la matchearía como un id y devolvería 422."""
    from .conftest import token_de

    ctx = armar_empresa()
    db.commit()
    r = client.get("/servicios/son-de-ejemplo", headers=token_de(ctx.dueno))
    assert r.status_code != 422, "La ruta la está capturando /{servicio_id}"
