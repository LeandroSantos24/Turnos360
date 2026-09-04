"""La transferencia de punta a punta: el negocio avisa, Leandro confirma.

POR QUÉ ESTE CIRCUITO NECESITA SUS PROPIOS TESTS
────────────────────────────────────────────────
El cobro por Mercado Pago lo confirma un webhook contra la API de MP: si el
código está bien, no hay forma de equivocarse. La transferencia no tiene nada
de eso. La verifica una PERSONA mirando el homebanking, y lo que esa persona
ve en pantalla es todo lo que tiene para decidir. Un error acá no lo corrige
ningún sistema: se descubre cuando el cliente reclama que pagó Pro y quedó en
Inicial, o cuando el mes cierra con un número que no da.

Los tres agujeros que había, tal cual los encontramos:

1. EL AVISO NO LLEGABA A LA PANTALLA DE COBRO. El diálogo se abría con el
   precio de LISTA precargado, no con lo que el negocio dijo que transfirió, y
   sin el número de comprobante a la vista. Confirmar un pago era un ejercicio
   de memoria.

2. NO HABÍA CON QUÉ COMPARAR. Para saber si el monto avisado estaba bien había
   que acordarse del precio pactado de ESA empresa, que puede no ser el de
   lista. El que tiene descuento es justo el que más fácil se cobra mal.

3. NO SE PODÍA INDICAR EL PLAN. Una transferencia hecha PARA pasar a Pro se
   registraba como cuota y dejaba al negocio en Inicial: plata cobrada,
   producto no entregado.

Lo que sigue verifica que los tres están tapados, y que el aviso sale de la
bandeja solo cuando la cuota quedó registrada de verdad.
"""

import datetime as dt
import uuid

import pytest

from app.core import planes
from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import SuperAdmin
from app.services import cobranza


@pytest.fixture()
def admin(db) -> dict:
    """Un super-admin real en la base + su token."""
    sa = SuperAdmin(
        nombre="Admin Transferencias",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _avisar(db, ctx, monto, referencia="OP-123456", quien="dueno@negocio.test"):
    cobranza.registrar_aviso(
        db,
        ctx.empresa,
        metodo="transferencia",
        monto=monto,
        referencia=referencia,
        avisado_por=quien,
    )
    db.commit()


def _bandeja(client, admin):
    r = client.get("/admin/cobranza/avisos", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


# ══════════════════════════════════════════════════════════════════════
#  1. El aviso llega con todo lo necesario para decidir
# ══════════════════════════════════════════════════════════════════════

def test_el_aviso_trae_lo_avisado_y_lo_esperado(client, db, armar_empresa, admin):
    """Los dos números que hay que comparar, en la misma fila.

    Sin el esperado, la bandeja dice «avisó $19.900» y no hay forma de saber
    si eso está bien sin abrir la ficha de la empresa.
    """
    ctx = armar_empresa("Peluquería Norte")
    ctx.empresa.plan = "pro"
    db.commit()
    _avisar(db, ctx, 19900)

    fila = _bandeja(client, admin)[0]
    assert fila["monto"] == 19900
    assert fila["monto_esperado"] == planes.GRILLA[planes.Plan.PRO].precio
    assert fila["plan_codigo"] == "pro"
    assert fila["coincide"] is True


def test_el_precio_pactado_es_el_esperado_no_el_de_lista(client, db, armar_empresa, admin):
    """El que tiene descuento es el que más fácil se cobra mal.

    Si la bandeja mostrara el precio de lista, todos los negocios con precio
    pactado aparecerían como «no coincide» — y el que mira aprende a ignorar
    la advertencia, que es peor que no tenerla.
    """
    ctx = armar_empresa("Con descuento")
    ctx.empresa.plan = "pro"
    ctx.empresa.precio_mensual = 15000
    db.commit()
    _avisar(db, ctx, 15000)

    fila = _bandeja(client, admin)[0]
    assert fila["monto_esperado"] == 15000
    assert fila["coincide"] is True


def test_un_monto_distinto_se_marca_para_revisar(client, db, armar_empresa, admin):
    """Transfirió de menos. Tiene que saltar a la vista, no salir en una resta."""
    ctx = armar_empresa("Transfirió de menos")
    ctx.empresa.plan = "pro"
    db.commit()
    _avisar(db, ctx, 10000)

    fila = _bandeja(client, admin)[0]
    assert fila["coincide"] is False
    assert fila["monto"] == 10000
    assert fila["monto_esperado"] == planes.GRILLA[planes.Plan.PRO].precio


def test_un_aviso_sin_monto_nunca_coincide(client, db, armar_empresa, admin):
    """Cargar el monto es opcional para el negocio. Un aviso vacío no puede
    dar «coincide»: no hay nada que haya coincidido."""
    ctx = armar_empresa("Sin monto")
    db.commit()
    _avisar(db, ctx, None)

    fila = _bandeja(client, admin)[0]
    assert fila["monto"] is None
    assert fila["coincide"] is False


def test_el_aviso_dice_quien_y_con_que_comprobante(client, db, armar_empresa, admin):
    """El comprobante es lo que se busca en el resumen del banco. Si no viaja
    hasta la pantalla, hay que ir a buscarlo a otro lado."""
    ctx = armar_empresa("Con comprobante")
    db.commit()
    _avisar(db, ctx, 11900, referencia="OP-99887766", quien="marta@negocio.test")

    fila = _bandeja(client, admin)[0]
    assert fila["referencia"] == "OP-99887766"
    assert fila["avisado_por"] == "marta@negocio.test"
    assert fila["empresa_nombre"] == "Con comprobante"


def test_la_bandeja_dice_cuando_vence(client, db, armar_empresa, admin):
    """Para saber si esta cuota renueva o rescata una cuenta vencida."""
    ctx = armar_empresa("Vence pronto")
    vence = dt.date.today() + dt.timedelta(days=2)
    ctx.empresa.suscripcion_vence = vence
    db.commit()
    _avisar(db, ctx, 11900)

    assert _bandeja(client, admin)[0]["vence"] == vence.isoformat()


# ══════════════════════════════════════════════════════════════════════
#  2. Confirmar el pago activa el plan que se compró
# ══════════════════════════════════════════════════════════════════════

def test_confirmar_con_plan_deja_a_la_empresa_en_ese_plan(client, db, armar_empresa, admin):
    """EL agujero de esta tanda.

    Transfirió para pasar a Pro. Sin `plan`, la cuota se anotaba y el negocio
    seguía en Inicial: se cobró la plata y no se entregó lo comprado.
    """
    ctx = armar_empresa("Sube a Pro")
    ctx.empresa.plan = "inicial"
    db.commit()
    _avisar(db, ctx, 19900)

    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 19900, "metodo": "transferencia", "plan": "pro"},
    )
    assert r.status_code in (200, 201), r.text

    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "pro"


def test_confirmar_sin_plan_no_toca_el_plan(client, db, armar_empresa, admin):
    """Una renovación normal no es un cambio de plan. El campo es opcional
    justamente para que el caso común no pueda mover nada."""
    ctx = armar_empresa("Renueva nomás")
    ctx.empresa.plan = "pro"
    db.commit()

    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 19900, "metodo": "transferencia"},
    )
    assert r.status_code in (200, 201), r.text

    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "pro"


def test_enterprise_se_activa_por_acá_y_solo_por_acá(client, db, armar_empresa, admin):
    """Enterprise no tiene precio de lista, así que no puede pasar por el
    cobro automático. Esta es su ÚNICA puerta — si el panel lo rechazara,
    activarlo requeriría tocar la base a mano."""
    ctx = armar_empresa("Cadena grande")
    db.commit()

    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 80000, "metodo": "transferencia", "plan": "enterprise"},
    )
    assert r.status_code in (200, 201), r.text

    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "enterprise"
    # Y sigue sin venderse solo: por el checkout no se puede contratar.
    assert not planes.se_vende_solo(planes.Plan.ENTERPRISE)


def test_un_plan_inventado_se_rechaza_en_vez_de_caer_a_gratuito(
    client, db, armar_empresa, admin
):
    """`plan_de` manda lo desconocido a GRATUITO. Sin esta validación, un typo
    («pró», «PRO2») le sacaría el plan pago a alguien que acaba de pagar."""
    ctx = armar_empresa("Typo")
    ctx.empresa.plan = "pro"
    db.commit()

    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 19900, "metodo": "transferencia", "plan": "pro2"},
    )
    assert r.status_code == 400, r.text

    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "pro"


# ══════════════════════════════════════════════════════════════════════
#  3. El aviso sale de la bandeja cuando —y solo cuando— se cobró
# ══════════════════════════════════════════════════════════════════════

def test_registrar_el_cobro_saca_el_aviso_de_la_bandeja(client, db, armar_empresa, admin):
    """Si quedara, al día siguiente no se sabe cuáles ya se confirmaron y se
    cobra dos veces la misma transferencia."""
    ctx = armar_empresa("Ya confirmada")
    db.commit()
    _avisar(db, ctx, 11900)
    assert len(_bandeja(client, admin)) == 1

    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 11900, "metodo": "transferencia"},
    )
    assert r.status_code in (200, 201), r.text

    assert _bandeja(client, admin) == []


def test_descartar_saca_el_aviso_sin_registrar_plata(client, db, armar_empresa, admin):
    """El pago que nunca apareció en el banco. Sale de la lista y NO deja
    cuota: si dejara, el MRR contaría plata que no entró."""
    ctx = armar_empresa("Nunca llegó")
    db.commit()
    _avisar(db, ctx, 11900)
    aviso_id = _bandeja(client, admin)[0]["id"]

    r = client.post(
        f"/admin/cobranza/avisos/{aviso_id}/descartar", headers=admin
    )
    assert r.status_code == 200, r.text

    assert _bandeja(client, admin) == []
    pagos = client.get(
        f"/admin/empresas/{ctx.empresa.id}/pagos", headers=admin
    ).json()
    assert pagos == []


def test_la_bandeja_solo_muestra_lo_pendiente(client, db, armar_empresa, admin):
    """Dos negocios avisaron, uno se confirmó. Queda el otro."""
    a = armar_empresa("Confirmada")
    b = armar_empresa("Todavía no")
    db.commit()
    _avisar(db, a, 11900)
    _avisar(db, b, 11900)
    assert len(_bandeja(client, admin)) == 2

    client.post(
        f"/admin/empresas/{a.empresa.id}/pagos",
        headers=admin,
        json={"monto": 11900, "metodo": "transferencia"},
    )

    quedan = _bandeja(client, admin)
    assert [f["empresa_nombre"] for f in quedan] == ["Todavía no"]
