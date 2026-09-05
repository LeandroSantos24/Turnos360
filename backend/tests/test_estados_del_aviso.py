"""En qué quedó cada transferencia, y por qué.

EL AGUJERO
Un aviso tenía un `resuelto` booleano y el resto se DEDUCÍA: resuelto con
pago_id = confirmada, resuelto sin pago_id = descartada. Dos problemas:

1. Deducir el estado de la AUSENCIA de otro dato es frágil. Cualquier camino
   que resuelva un aviso sin registrar la cuota queda indistinguible de un
   rechazo, y son cosas muy distintas cuando el negocio pregunta.

2. No había lugar para el POR QUÉ. Un aviso descartado desaparecía de la
   bandeja sin dejar nada: ni quién, ni cuándo, ni por qué. Si el negocio
   reclamaba a la semana siguiente, no había con qué contestarle.

`resuelto` se eliminó en vez de convivir con `estado`: dos columnas que dicen
lo mismo se desincronizan el día que un camino toca una y no la otra, y ahí la
bandeja muestra un aviso ya cobrado o esconde uno que falta cobrar.
"""

import uuid

import pytest

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import AvisoPago, SuperAdmin
from app.services import cobranza


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(
        nombre="Admin Estados",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _avisar(db, ctx, monto=19900):
    a = cobranza.registrar_aviso(
        db, ctx.empresa, metodo="transferencia", monto=monto,
        referencia="OP-1", avisado_por="dueno@negocio.test",
    )
    db.commit()
    return a


def _bandeja(client, admin, pendientes=True):
    r = client.get(f"/admin/cobranza/avisos?pendientes={str(pendientes).lower()}", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


# ══════════════════════════════════════════════════════════════════════
#  Los tres estados
# ══════════════════════════════════════════════════════════════════════

def test_un_aviso_nace_pendiente(db, armar_empresa):
    ctx = armar_empresa()
    a = _avisar(db, ctx)
    assert a.estado == cobranza.PENDIENTE
    assert a.resuelto is False, "La propiedad derivada tiene que seguir el estado."


def test_cobrar_lo_deja_confirmado_y_atado_a_la_cuota(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    aviso = _avisar(db, ctx)

    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 19900, "metodo": "transferencia"},
    )
    assert r.status_code in (200, 201), r.text

    db.expire_all()
    vuelto = db.get(AvisoPago, aviso.id)
    assert vuelto.estado == cobranza.CONFIRMADA
    assert vuelto.pago_id is not None, "Confirmada tiene que señalar la cuota."
    assert vuelto.resuelto is True


def test_rechazar_guarda_el_motivo(client, db, armar_empresa, admin):
    """EL punto de todo esto: cuando el negocio pregunte, hay qué contestarle."""
    ctx = armar_empresa()
    aviso = _avisar(db, ctx)

    r = client.post(
        f"/admin/cobranza/avisos/{aviso.id}/descartar",
        headers=admin,
        json={"motivo": "No apareció en el banco en 5 días"},
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    vuelto = db.get(AvisoPago, aviso.id)
    assert vuelto.estado == cobranza.RECHAZADA
    assert vuelto.motivo == "No apareció en el banco en 5 días"
    assert vuelto.resuelto_por is not None, "Y quién lo rechazó."
    assert vuelto.resuelto_en is not None, "Y cuándo."
    assert vuelto.pago_id is None, "Rechazar NO registra plata."


def test_rechazar_sin_motivo_igual_funciona(client, db, armar_empresa, admin):
    """El motivo se pide pero no se exige: frenar a quien solo quiere limpiar
    la bandeja convertiría el campo en un obstáculo y se llenaría de «.»."""
    ctx = armar_empresa()
    aviso = _avisar(db, ctx)

    r = client.post(f"/admin/cobranza/avisos/{aviso.id}/descartar", headers=admin)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(AvisoPago, aviso.id).estado == cobranza.RECHAZADA


def test_rechazar_no_registra_ninguna_cuota(client, db, armar_empresa, admin):
    """Si registrara, el MRR contaría plata que nunca entró."""
    ctx = armar_empresa()
    aviso = _avisar(db, ctx)
    client.post(
        f"/admin/cobranza/avisos/{aviso.id}/descartar",
        headers=admin, json={"motivo": "nunca llegó"},
    )
    pagos = client.get(f"/admin/empresas/{ctx.empresa.id}/pagos", headers=admin).json()
    assert pagos == []


# ══════════════════════════════════════════════════════════════════════
#  La bandeja
# ══════════════════════════════════════════════════════════════════════

def test_la_bandeja_solo_trae_pendientes(client, db, armar_empresa, admin):
    a = armar_empresa("Se rechaza")
    b = armar_empresa("Sigue esperando")
    db.commit()
    aviso_a = _avisar(db, a)
    _avisar(db, b)
    assert len(_bandeja(client, admin)) == 2

    client.post(
        f"/admin/cobranza/avisos/{aviso_a.id}/descartar",
        headers=admin, json={"motivo": "no llegó"},
    )
    quedan = _bandeja(client, admin)
    assert [f["empresa_nombre"] for f in quedan] == ["Sigue esperando"]


def test_el_historial_completo_muestra_el_estado_y_el_motivo(client, db, armar_empresa, admin):
    """Con pendientes=false salen todos: es donde se va a mirar cuando el
    negocio reclame por un mes que dice haber pagado."""
    ctx = armar_empresa("Reclamó")
    aviso = _avisar(db, ctx)
    client.post(
        f"/admin/cobranza/avisos/{aviso.id}/descartar",
        headers=admin, json={"motivo": "vino por $5.000, no por $19.900"},
    )

    fila = next(f for f in _bandeja(client, admin, pendientes=False) if f["id"] == aviso.id)
    assert fila["estado"] == "rechazada"
    assert fila["motivo"] == "vino por $5.000, no por $19.900"


def test_resolver_dos_veces_no_pisa_el_primero(client, db, armar_empresa, admin):
    """Confirmar y después descartar no puede convertir una cuota cobrada en un
    rechazo: la plata ya entró y la fila la señala."""
    ctx = armar_empresa()
    aviso = _avisar(db, ctx)
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin, json={"monto": 19900, "metodo": "transferencia"},
    )
    client.post(
        f"/admin/cobranza/avisos/{aviso.id}/descartar",
        headers=admin, json={"motivo": "me confundí"},
    )

    db.expire_all()
    vuelto = db.get(AvisoPago, aviso.id)
    assert vuelto.estado == cobranza.CONFIRMADA
    assert vuelto.pago_id is not None


def test_un_negocio_no_puede_rechazar_sus_propios_avisos(client, db, armar_empresa):
    ctx = armar_empresa()
    aviso = _avisar(db, ctx)
    r = client.post(f"/admin/cobranza/avisos/{aviso.id}/descartar")
    assert r.status_code in (401, 403)
