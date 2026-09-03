"""Toda empresa nace con con qué cobrar, y Mercado Pago se encuentra por clave.

DOS PROBLEMAS QUE ESTOS TESTS FIJAN
───────────────────────────────────
1. La tabla `metodo_pago` arrancaba vacía. Un negocio recién dado de alta
   entraba a Finanzas y leía «Todavía no cargaste métodos. Empezá con Efectivo,
   Débito, Transferencia…»: le pedíamos que escribiera de memoria los mismos
   cinco nombres que escribe todo el mundo, y hasta que no lo hacía no podía
   registrar un solo cobro.

2. `_metodo_mercado_pago()` —el que decide dónde entra la plata de cada seña—
   buscaba `lower(nombre) == "mercado pago"`. Si alguien renombraba su método
   «MP», el match fallaba y la función creaba uno NUEVO en silencio: dos
   métodos de Mercado Pago, la plata de las señas repartida entre los dos, y la
   caja cuadrando mal sin que nada tirara un error.
"""

from sqlalchemy import select

from app.models.finanzas import MetodoPago
from app.services import metodos_pago as svc
from app.services.finanzas import _metodo_mercado_pago


def _metodos_de(db, empresa_id) -> list[MetodoPago]:
    return list(
        db.scalars(
            select(MetodoPago)
            .where(MetodoPago.empresa_id == empresa_id)
            .order_by(MetodoPago.orden, MetodoPago.id)
        )
    )


# ── El sembrado ──────────────────────────────────────────────────────────

def test_una_empresa_nueva_ya_puede_cobrar(db, armar_empresa):
    """Lo que importa: no hay un paso previo antes del primer cobro."""
    a = armar_empresa("Recién nacida")
    svc.sembrar(db, a.empresa.id)
    db.flush()

    claves = {m.clave for m in _metodos_de(db, a.empresa.id) if m.clave}
    assert claves == {"efectivo", "debito", "credito", "transferencia", "mp_qr"}


def test_los_cinco_vienen_prendidos_y_en_el_orden_del_mostrador(db, armar_empresa):
    """Efectivo primero. Alfabético arrancaría por «Crédito», que es el que
    menos se toca."""
    a = armar_empresa("Orden")
    svc.sembrar(db, a.empresa.id)
    db.flush()

    de_fabrica = [m for m in _metodos_de(db, a.empresa.id) if m.clave]
    assert [m.clave for m in de_fabrica] == [
        "efectivo", "debito", "credito", "transferencia", "mp_qr",
    ]
    assert all(m.activo for m in de_fabrica)


def test_efectivo_y_transferencia_no_cobran_comision(db, armar_empresa):
    a = armar_empresa("Comisiones")
    svc.sembrar(db, a.empresa.id)
    db.flush()

    por_clave = {m.clave: m for m in _metodos_de(db, a.empresa.id) if m.clave}
    assert float(por_clave["efectivo"].comision_pct) == 0
    assert float(por_clave["transferencia"].comision_pct) == 0
    # Y los que sí cobran, arrancan con algo cargado: el dueño lo corrige, no
    # lo inventa desde cero.
    assert float(por_clave["credito"].comision_pct) > 0
    assert float(por_clave["mp_qr"].comision_pct) > 0


def test_sembrar_dos_veces_no_duplica_ni_pisa_lo_ajustado(db, armar_empresa):
    """Idempotente. Importa para el día que agreguemos un sexto medio y haya
    que sumárselo a las empresas que ya existen sin tocarles su configuración."""
    a = armar_empresa("Idempotente")
    svc.sembrar(db, a.empresa.id)
    db.flush()

    efectivo = svc.por_clave(db, a.empresa.id, "efectivo")
    efectivo.nombre = "Contado"
    credito = svc.por_clave(db, a.empresa.id, "credito")
    credito.comision_pct = 9.9
    db.flush()

    svc.sembrar(db, a.empresa.id)
    db.flush()

    de_fabrica = [m for m in _metodos_de(db, a.empresa.id) if m.clave]
    assert len(de_fabrica) == 5
    assert svc.por_clave(db, a.empresa.id, "efectivo").nombre == "Contado"
    assert float(svc.por_clave(db, a.empresa.id, "credito").comision_pct) == 9.9


def test_cada_empresa_tiene_los_suyos(db, armar_empresa):
    """Regla 1: nada se comparte entre negocios, tampoco esto."""
    a = armar_empresa("Empresa A")
    b = armar_empresa("Empresa B")
    svc.sembrar(db, a.empresa.id)
    svc.sembrar(db, b.empresa.id)
    db.flush()

    de_a = svc.por_clave(db, a.empresa.id, "efectivo")
    de_b = svc.por_clave(db, b.empresa.id, "efectivo")
    assert de_a is not None and de_b is not None
    assert de_a.id != de_b.id


# ── El match de Mercado Pago ─────────────────────────────────────────────

def test_mercado_pago_se_encuentra_aunque_lo_renombren(db, armar_empresa):
    """EL test de este archivo.

    Antes se buscaba por nombre. Renombrar el método a «MP» hacía que la
    siguiente seña creara un método nuevo, y la plata quedaba repartida entre
    dos «Mercado Pago» sin que nada avisara.
    """
    a = armar_empresa("Renombrado")
    svc.sembrar(db, a.empresa.id)
    db.flush()

    mp = svc.por_clave(db, a.empresa.id, "mp_qr")
    mp.nombre = "MP"  # el dueño lo acorta desde la pantalla
    db.flush()

    encontrado = _metodo_mercado_pago(db, a.empresa.id)

    assert encontrado.id == mp.id, "creó un método nuevo en vez de usar el suyo"
    assert len([m for m in _metodos_de(db, a.empresa.id) if m.clave == "mp_qr"]) == 1


def test_una_empresa_sin_sembrar_igual_cobra_su_sena(db, armar_empresa):
    """Empresas dadas de alta antes del sembrado: perder el registro de una
    seña ya cobrada es peor que crear métodos de más."""
    a = armar_empresa("Vieja")
    db.query(MetodoPago).filter_by(empresa_id=a.empresa.id).delete()
    db.flush()

    metodo = _metodo_mercado_pago(db, a.empresa.id)

    assert metodo is not None
    assert metodo.clave == "mp_qr"


# ── Sacar un método de circulación ───────────────────────────────────────

def test_un_metodo_de_fabrica_se_apaga_no_se_borra(db, armar_empresa):
    """Un negocio que este mes no usó efectivo no debería quedarse sin la
    forma de cobro más común y sin manera obvia de recuperarla."""
    from app.services.finanzas import borrar_metodo

    a = armar_empresa("Apagar")
    svc.sembrar(db, a.empresa.id)
    db.flush()
    efectivo = svc.por_clave(db, a.empresa.id, "efectivo")

    assert borrar_metodo(db, a.empresa.id, efectivo.id) is True

    sigue = svc.por_clave(db, a.empresa.id, "efectivo")
    assert sigue is not None, "se borró un método de fábrica"
    assert sigue.activo is False


def test_un_metodo_propio_sin_uso_si_se_borra(db, armar_empresa):
    """Si no tiene historia y lo creó el dueño, borrarlo de verdad es lo que
    la persona espera: se equivocó al cargarlo y lo quiere fuera."""
    from app.services.finanzas import borrar_metodo

    a = armar_empresa("Borrar")
    propio = MetodoPago(empresa_id=a.empresa.id, nombre="Ualá", comision_pct=3)
    db.add(propio)
    db.flush()
    propio_id = propio.id

    assert borrar_metodo(db, a.empresa.id, propio_id) is True
    assert db.get(MetodoPago, propio_id) is None


def test_un_metodo_propio_con_cobros_se_apaga(db, armar_empresa):
    """Borrarlo dejaría la caja de esos días con plata sin método."""
    import datetime as dt

    from app.models.enums import TipoMovimiento
    from app.models.finanzas import MovimientoFinanciero
    from app.services.finanzas import borrar_metodo

    a = armar_empresa("Con historia")
    propio = MetodoPago(empresa_id=a.empresa.id, nombre="Ualá", comision_pct=3)
    db.add(propio)
    db.flush()

    db.add(
        MovimientoFinanciero(
            empresa_id=a.empresa.id,
            sucursal_id=a.sede.id,
            tipo=TipoMovimiento.INGRESO,
            concepto="Corte",
            monto=10000,
            metodo_pago_id=propio.id,
            fecha=dt.datetime.now(dt.timezone.utc),
        )
    )
    db.flush()

    assert borrar_metodo(db, a.empresa.id, propio.id) is True

    sigue = db.get(MetodoPago, propio.id)
    assert sigue is not None, "se borró un método con cobros: la caja pierde el dato"
    assert sigue.activo is False
