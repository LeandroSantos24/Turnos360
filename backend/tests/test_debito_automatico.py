"""El débito automático: «pagás la suscripción y listo».

QUÉ SE VERIFICA ACÁ, Y POR QUÉ ASÍ
──────────────────────────────────
Nada de esto puede probarse contra Mercado Pago de verdad: haría falta una
cuenta, una tarjeta y una URL pública, y aun teniéndolas los tests dependerían
de que MP esté arriba. Lo que sí se puede —y es donde están los errores caros—
es verificar QUÉ HACEMOS NOSOTROS con cada respuesta posible.

Las llamadas HTTP se reemplazan por funciones que devuelven exactamente los
cuerpos que documenta Mercado Pago. Eso deja verificar lo que importa:

  · que un cobro rechazado NO acredite plata;
  · que el mismo cobro notificado dos veces no corra 60 días;
  · que una empresa no pueda terminar con dos débitos vivos;
  · que cancelar no le apague el servicio a alguien que ya pagó el mes;
  · que el webhook mande cada tipo de aviso al lugar correcto.

Lo que NO puede verificar un test así: que los cuerpos que devuelve MP sean
realmente estos. Eso se confirma la primera vez que entre un cobro real.
"""

import datetime as dt
import uuid

import pytest

from app.core import planes
from app.models import DebitoAutomatico, PagoSuscripcion
from app.services import mp_debito
from app.services.suscripcion import DIAS_PRORROGA
from tests.conftest import token_de


# ══════════════════════════════════════════════════════════════════════
#  Dobles de Mercado Pago
# ══════════════════════════════════════════════════════════════════════

def _prender(monkeypatch):
    """Hace de cuenta que hay token del SaaS configurado."""
    monkeypatch.setattr(mp_debito, "esta_activo", lambda: True)


def _suscripcion(db, empresa, plan="pro", estado=mp_debito.ACTIVO, preapproval=None):
    """Una fila de débito automático ya creada, como la dejaría `crear()`."""
    fila = DebitoAutomatico(
        empresa_id=empresa.id,
        preapproval_id=preapproval or uuid.uuid4().hex,
        estado=estado,
        plan=plan,
        monto=planes.GRILLA[planes.plan_de(plan)].precio,
    )
    db.add(fila)
    db.flush()
    return fila


def _cobro(fila, *, estado_pago="approved", payment_id=None, monto=None, detalle=None):
    """El cuerpo de GET /authorized_payments/{id}, como lo documenta MP."""
    return {
        "id": 19951520999,
        "type": "scheduled",
        "preapproval_id": fila.preapproval_id,
        "external_reference": mp_debito.referencia_de(fila.empresa_id, fila.plan),
        "currency_id": "ARS",
        "transaction_amount": monto if monto is not None else float(fila.monto),
        "debit_date": dt.date.today().isoformat(),
        "retry_attempt": 0,
        "status": "processed",
        "payment": {
            "id": payment_id or int(uuid.uuid4().int % 10**9),
            "status": estado_pago,
            "status_detail": detalle or ("accredited" if estado_pago == "approved" else "cc_rejected_bad_filled_date"),
        },
    }


# ══════════════════════════════════════════════════════════════════════
#  1. El cobro mensual: lo único que hace que el "y listo" sea cierto
# ══════════════════════════════════════════════════════════════════════

def test_un_cobro_aprobado_corre_el_vencimiento_y_activa_el_plan(
    db, armar_empresa, monkeypatch
):
    """El mes se paga solo: nadie transfiere, nadie avisa, nadie registra."""
    ctx = armar_empresa()
    ctx.empresa.plan = "inicial"
    ctx.empresa.suscripcion_vence = dt.date.today()
    db.flush()

    fila = _suscripcion(db, ctx.empresa, plan="pro")
    _prender(monkeypatch)
    monkeypatch.setattr(mp_debito, "consultar_cobro", lambda _id: _cobro(fila))

    pago = mp_debito.acreditar_cobro(db, "19951520999")

    assert pago is not None, "Un cobro aprobado tiene que acreditarse."
    assert pago.metodo == "debito_automatico"
    assert ctx.empresa.plan == "pro", "El plan que paga la suscripción se activa solo."
    assert ctx.empresa.suscripcion_vence > dt.date.today()


def test_un_cobro_rechazado_no_acredita_nada_pero_deja_el_motivo(
    db, armar_empresa, monkeypatch
):
    """LA regla: sin plata acreditada, pero sin silencio.

    El dueño tiene que poder enterarse de que su tarjeta rebotó ANTES de que
    se le corte el servicio. Si el rechazo no dejara rastro, el primer aviso
    sería la agenda apagada.
    """
    ctx = armar_empresa()
    vencia = dt.date.today() + dt.timedelta(days=2)
    ctx.empresa.suscripcion_vence = vencia
    db.flush()

    fila = _suscripcion(db, ctx.empresa)
    _prender(monkeypatch)
    monkeypatch.setattr(
        mp_debito,
        "consultar_cobro",
        lambda _id: _cobro(fila, estado_pago="rejected", detalle="cc_rejected_insufficient_amount"),
    )

    assert mp_debito.acreditar_cobro(db, "19951520999") is None
    db.refresh(fila)
    assert fila.cobros_fallidos == 1
    assert "insufficient" in (fila.ultimo_error or "")
    assert ctx.empresa.suscripcion_vence == vencia, (
        "Un cobro rechazado NO puede correr el vencimiento."
    )


def test_el_mismo_cobro_notificado_dos_veces_paga_un_mes_solo(
    db, armar_empresa, monkeypatch
):
    """Mercado Pago reintenta la misma notificación varias veces.

    Sin idempotencia, cada reintento corre otros 30 días: el negocio termina
    con seis meses pagos por un mes cobrado, y se descubre auditando.
    """
    ctx = armar_empresa()
    ctx.empresa.suscripcion_vence = dt.date.today()
    db.flush()

    fila = _suscripcion(db, ctx.empresa)
    _prender(monkeypatch)
    cuerpo = _cobro(fila, payment_id=777000111)
    monkeypatch.setattr(mp_debito, "consultar_cobro", lambda _id: cuerpo)

    primero = mp_debito.acreditar_cobro(db, "19951520999")
    vence_tras_el_primero = ctx.empresa.suscripcion_vence
    segundo = mp_debito.acreditar_cobro(db, "19951520999")

    assert primero is not None
    assert segundo is None, "El segundo aviso del mismo cobro no acredita nada."
    assert ctx.empresa.suscripcion_vence == vence_tras_el_primero

    cuotas = (
        db.query(PagoSuscripcion)
        .filter(PagoSuscripcion.mp_payment_id == "777000111")
        .count()
    )
    assert cuotas == 1


def test_un_cobro_que_vuelve_a_salir_bien_limpia_el_cartel_de_error(
    db, armar_empresa, monkeypatch
):
    """Si el motivo del rechazo viejo no se borrara, el panel seguiría
    diciendo «tu tarjeta venció» con la cuota del mes ya cobrada."""
    ctx = armar_empresa()
    fila = _suscripcion(db, ctx.empresa)
    fila.cobros_fallidos = 2
    fila.ultimo_error = "cc_rejected_bad_filled_date"
    db.flush()

    _prender(monkeypatch)
    monkeypatch.setattr(mp_debito, "consultar_cobro", lambda _id: _cobro(fila))
    mp_debito.acreditar_cobro(db, "19951520999")

    db.refresh(fila)
    assert fila.cobros_fallidos == 0
    assert fila.ultimo_error is None


def test_un_cobro_de_una_suscripcion_que_no_es_nuestra_se_ignora(
    db, armar_empresa, monkeypatch
):
    """La cuenta de Mercado Pago puede tener suscripciones de otra cosa.

    Acreditar contra un preapproval que no está en nuestra tabla significaría
    inventar de qué empresa es el cobro.
    """
    ctx = armar_empresa()
    fila = _suscripcion(db, ctx.empresa)
    ajeno = _cobro(fila)
    ajeno["preapproval_id"] = "2c93808400000000000000000000ffff"

    _prender(monkeypatch)
    monkeypatch.setattr(mp_debito, "consultar_cobro", lambda _id: ajeno)

    assert mp_debito.acreditar_cobro(db, "19951520999") is None


# ══════════════════════════════════════════════════════════════════════
#  2. Activar: una sola suscripción viva por empresa
# ══════════════════════════════════════════════════════════════════════

def test_no_se_pueden_tener_dos_debitos_vivos(db, armar_empresa, monkeypatch):
    """Dos autorizaciones sobre la misma tarjeta = dos cargos por mes.

    Alcanza un doble click en «Activar», o el doble render de React en
    desarrollo. Lo frena el índice único parcial de la base y no el código
    porque entre el SELECT que comprueba y el INSERT que crea hay una ventana.
    """
    from sqlalchemy.exc import IntegrityError

    ctx = armar_empresa()
    _suscripcion(db, ctx.empresa, preapproval="aaaa1111bbbb2222")

    with pytest.raises(IntegrityError):
        _suscripcion(db, ctx.empresa, preapproval="cccc3333dddd4444")
    db.rollback()


def test_una_cancelada_no_bloquea_activar_de_nuevo(db, armar_empresa):
    """El que canceló tiene que poder volver. El índice es PARCIAL justamente
    para eso: las canceladas no ocupan lugar."""
    ctx = armar_empresa()
    vieja = _suscripcion(db, ctx.empresa, preapproval="aaaa1111bbbb2222")
    vieja.estado = mp_debito.CANCELADO
    db.flush()

    nueva = _suscripcion(db, ctx.empresa, preapproval="cccc3333dddd4444")
    assert nueva.id is not None
    assert mp_debito.vigente(db, ctx.empresa.id).id == nueva.id


def test_el_endpoint_frena_el_segundo_intento_con_un_mensaje(
    client, db, armar_empresa, monkeypatch
):
    """Antes de chocar contra la base, el panel dice qué pasa y qué hacer."""
    ctx = armar_empresa()
    _suscripcion(db, ctx.empresa)
    db.commit()
    _prender(monkeypatch)

    r = client.post(
        "/empresa/suscripcion/debito-automatico?plan=pro", headers=token_de(ctx.dueno)
    )
    assert r.status_code == 409
    assert "cancelalo primero" in r.json()["detail"].lower()


def test_enterprise_no_se_puede_poner_en_debito_automatico(
    client, db, armar_empresa, monkeypatch
):
    """No tiene precio de lista: autorizar un débito por Enterprise cobraría
    el precio de otro plan."""
    ctx = armar_empresa()
    db.commit()
    _prender(monkeypatch)

    r = client.post(
        "/empresa/suscripcion/debito-automatico?plan=enterprise",
        headers=token_de(ctx.dueno),
    )
    assert r.status_code == 400


def test_sin_token_de_mp_el_endpoint_lo_explica(client, db, armar_empresa, monkeypatch):
    """En local no hay token. Un 500 haría pensar que algo se rompió."""
    ctx = armar_empresa()
    db.commit()
    monkeypatch.setattr(mp_debito, "esta_activo", lambda: False)

    r = client.post(
        "/empresa/suscripcion/debito-automatico?plan=pro", headers=token_de(ctx.dueno)
    )
    assert r.status_code == 503
    assert "transferencia" in r.json()["detail"].lower()


# ══════════════════════════════════════════════════════════════════════
#  3. Cancelar: cortar el cobro sin cortar el servicio
# ══════════════════════════════════════════════════════════════════════

def test_cancelar_no_le_saca_el_mes_que_ya_pago(db, armar_empresa, monkeypatch):
    """Cortar en el acto algo que está pagado se siente como un robo."""
    ctx = armar_empresa()
    vence = dt.date.today() + dt.timedelta(days=18)
    ctx.empresa.suscripcion_vence = vence
    db.flush()
    fila = _suscripcion(db, ctx.empresa)

    _prender(monkeypatch)
    monkeypatch.setattr(
        mp_debito.httpx, "put", lambda *a, **k: _RespuestaOk()
    )

    assert mp_debito.cancelar(db, ctx.empresa.id, quien="dueno@test") is True
    db.refresh(fila)
    db.refresh(ctx.empresa)
    assert fila.estado == mp_debito.CANCELADO
    assert ctx.empresa.suscripcion_vence == vence, (
        "El servicio sigue hasta el final del mes que ya se cobró."
    )


def test_si_mercado_pago_no_acepta_la_baja_no_la_damos_por_hecha(
    db, armar_empresa, monkeypatch
):
    """EL orden importa. Si marcáramos la fila primero, un error de red
    dejaría el panel diciendo «cancelado» mientras MP sigue cobrando todos los
    meses — el peor de los dos errores posibles."""
    ctx = armar_empresa()
    fila = _suscripcion(db, ctx.empresa)

    _prender(monkeypatch)

    def _explota(*a, **k):
        raise RuntimeError("MP caído")

    monkeypatch.setattr(mp_debito.httpx, "put", _explota)

    assert mp_debito.cancelar(db, ctx.empresa.id, quien="dueno@test") is False
    db.refresh(fila)
    assert fila.estado == mp_debito.ACTIVO, "La fila queda como estaba."


class _RespuestaOk:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"status": "cancelled"}


# ══════════════════════════════════════════════════════════════════════
#  4. Sincronizar: enterarse de lo que pasa sin nosotros
# ══════════════════════════════════════════════════════════════════════

def test_cuando_el_dueno_termina_de_poner_la_tarjeta_pasa_a_activo(
    db, armar_empresa, monkeypatch
):
    ctx = armar_empresa()
    fila = _suscripcion(db, ctx.empresa, estado=mp_debito.PENDIENTE)
    db.commit()

    _prender(monkeypatch)
    monkeypatch.setattr(
        mp_debito,
        "consultar",
        lambda _id: {
            "status": "authorized",
            "next_payment_date": "2026-10-06T13:07:14.260Z",
        },
    )

    mp_debito.sincronizar(db, fila.preapproval_id)
    db.refresh(fila)
    assert fila.estado == mp_debito.ACTIVO
    assert fila.proximo_cobro == dt.date(2026, 10, 6)


def test_si_mp_no_responde_la_fila_queda_como_estaba(db, armar_empresa, monkeypatch):
    """Marcar cancelada una suscripción por un timeout le apagaría el débito a
    alguien que lo tiene andando."""
    ctx = armar_empresa()
    fila = _suscripcion(db, ctx.empresa)
    db.commit()

    _prender(monkeypatch)
    monkeypatch.setattr(mp_debito, "consultar", lambda _id: None)

    mp_debito.sincronizar(db, fila.preapproval_id)
    db.refresh(fila)
    assert fila.estado == mp_debito.ACTIVO


def test_una_baja_hecha_por_mercado_pago_queda_registrada_como_tal(
    db, armar_empresa, monkeypatch
):
    """MP da de baja sola la suscripción tras tres ciclos rechazados. Saber
    que la cortó MP —y no el dueño— es la diferencia entre «se fue» y «se le
    venció la tarjeta», que son dos llamados muy distintos."""
    ctx = armar_empresa()
    fila = _suscripcion(db, ctx.empresa)
    db.commit()

    _prender(monkeypatch)
    monkeypatch.setattr(mp_debito, "consultar", lambda _id: {"status": "cancelled"})

    mp_debito.sincronizar(db, fila.preapproval_id)
    db.refresh(fila)
    assert fila.estado == mp_debito.CANCELADO
    assert fila.cancelada_por == "mercadopago"
    assert fila.cancelada_en is not None


# ══════════════════════════════════════════════════════════════════════
#  5. El webhook manda cada aviso a donde va
# ══════════════════════════════════════════════════════════════════════

def _llamadas(monkeypatch):
    """Reemplaza los tres destinos y anota cuál se llamó."""
    vistas: list[tuple[str, str]] = []
    from app.routers import publico as router_publico

    monkeypatch.setattr(
        router_publico.mp_sus, "acreditar",
        lambda db, ident: vistas.append(("pago_suelto", ident)),
    )
    monkeypatch.setattr(
        router_publico.mp_debito, "acreditar_cobro",
        lambda db, ident: vistas.append(("cobro_mensual", ident)),
    )
    monkeypatch.setattr(
        router_publico.mp_debito, "sincronizar",
        lambda db, ident: vistas.append(("sincronizar", ident)),
    )
    monkeypatch.setattr(router_publico.mp_sus, "esta_activo", lambda: True)
    return vistas


@pytest.mark.parametrize(
    "tipo, ident, destino",
    [
        ("payment", "123456789", "pago_suelto"),
        ("subscription_authorized_payment", "19951520999", "cobro_mensual"),
        ("subscription_preapproval", "2c938084726fca480172750000000000", "sincronizar"),
    ],
)
def test_cada_tipo_de_aviso_va_a_su_lugar(client, monkeypatch, tipo, ident, destino):
    """EL BUG QUE ESTO PROTEGE, que es sutil y silencioso.

    El filtro del webhook era `if "payment" not in tipo`. La palabra "payment"
    está DENTRO de `subscription_authorized_payment`, así que el cobro mensual
    de un débito automático pasaba el filtro y se trataba como un pago suelto:
    su id se buscaba en /v1/payments, donde no existe, la consulta volvía 404,
    y la función devolvía None sin quejarse.

    Resultado: el débito automático cobraba todos los meses en Mercado Pago y
    el vencimiento del negocio no se movía nunca. Nada falla, nadie se entera,
    y el cliente que paga religiosamente aparece como moroso.
    """
    vistas = _llamadas(monkeypatch)

    r = client.post(
        f"/publico/mp/webhook-suscripcion?type={tipo}&data.id={ident}"
    )
    assert r.status_code == 200
    assert vistas == [(destino, ident)], (
        f"Un aviso «{tipo}» tiene que ir a {destino} y a ningún otro lado."
    )


def test_un_id_de_suscripcion_hexadecimal_no_se_descarta(client, monkeypatch):
    """Los ids de preapproval NO son números: son hexadecimal.

    La primera versión del despacho les aplicaba el mismo `.isdigit()` que a
    los pagos. Eso habría descartado TODAS las notificaciones de suscripción
    en silencio: el débito se activaba en Mercado Pago y el panel nunca se
    enteraba de que la tarjeta ya estaba puesta.
    """
    vistas = _llamadas(monkeypatch)

    client.post(
        "/publico/mp/webhook-suscripcion"
        "?type=subscription_preapproval&data.id=2c938084726fca480172750000000000"
    )
    assert len(vistas) == 1, "El id hexadecimal tiene que pasar el filtro."


def test_un_aviso_de_un_tipo_que_no_manejamos_se_ignora_sin_romper(client, monkeypatch):
    """A Mercado Pago SIEMPRE se le contesta 200 o reintenta para siempre."""
    vistas = _llamadas(monkeypatch)

    r = client.post(
        "/publico/mp/webhook-suscripcion?type=subscription_preapproval_plan&data.id=abc123def456"
    )
    assert r.status_code == 200
    assert vistas == []


# ══════════════════════════════════════════════════════════════════════
#  6. Lo que ve el dueño
# ══════════════════════════════════════════════════════════════════════

def test_la_pantalla_recibe_el_estado_del_debito(client, db, armar_empresa, monkeypatch):
    ctx = armar_empresa()
    ctx.empresa.plan = "pro"
    _suscripcion(db, ctx.empresa, plan="pro")
    db.commit()
    _prender(monkeypatch)

    datos = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    assert datos["debito"]["estado"] == "authorized"
    assert datos["debito"]["monto"] == planes.GRILLA[planes.Plan.PRO].precio
    assert datos["debito"]["plan_etiqueta"] == "Pro"


def test_sin_debito_el_campo_viene_en_null(client, db, armar_empresa):
    """None = «no tenés», que es lo que hace que la pantalla ofrezca activarlo.
    Un dict vacío obligaría a adivinar."""
    ctx = armar_empresa()
    db.commit()

    datos = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    assert datos["debito"] is None


def test_la_prorroga_que_se_le_promete_al_dueno_es_la_que_se_aplica(
    client, db, armar_empresa
):
    """El número del cartel y el que decide el corte tienen que ser el mismo.

    Estuvieron separados: el schema tenía `dias_prorroga: int = 10` escrito a
    mano mientras la constante bajaba a 3. Un default viejo le habría
    prometido siete días que ya no existen.
    """
    ctx = armar_empresa()
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=5)
    db.commit()

    datos = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    assert datos["dias_prorroga"] == DIAS_PRORROGA == 3

    corte = dt.date.fromisoformat(datos["corte"])
    vence = dt.date.fromisoformat(datos["vence"])
    assert (corte - vence).days == DIAS_PRORROGA


# ══════════════════════════════════════════════════════════════════════
#  7. El "y listo" también significa dejar de escribirle
# ══════════════════════════════════════════════════════════════════════

def _correr_avisos(db, monkeypatch):
    """Corre el barrido diario de cobranza contra ESTA sesión de test.

    La tarea abre su propia sesión con `SessionLocal`, que en un test sale de
    la transacción que se revierte al final: sin este reemplazo, no vería
    ninguna de las empresas creadas por el test.
    """
    from contextlib import contextmanager

    from app.tasks import emails as mod

    @contextmanager
    def _sesion():
        yield db

    monkeypatch.setattr(mod, "SessionLocal", _sesion)

    mandados: list[tuple[int, str]] = []
    monkeypatch.setattr(
        mod,
        "_mandar",
        lambda db_, empresa, destino, asunto, html, marca: mandados.append(
            (empresa.id, asunto)
        ),
    )
    mod.avisar_vencimientos()
    return mandados


def test_al_que_paga_solo_no_se_le_avisa_que_vence(db, armar_empresa, monkeypatch):
    """ES LO QUE HACE CIERTO EL «Y LISTO».

    Mandarle «tu suscripción vence en 3 días» a alguien cuya tarjeta se va a
    cobrar sola es pedirle que se preocupe por algo que ya resolvió. Netflix
    no te avisa que vence: te cobra.
    """
    ctx = armar_empresa()
    ctx.empresa.prueba_hasta = None
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=3)
    db.flush()
    _suscripcion(db, ctx.empresa, estado=mp_debito.ACTIVO)
    db.flush()

    mandados = _correr_avisos(db, monkeypatch)
    assert not [m for m in mandados if m[0] == ctx.empresa.id]


def test_al_que_tiene_el_debito_rebotado_SÍ_se_le_avisa(db, armar_empresa, monkeypatch):
    """La excepción, y es la que importa: acá el débito no va a resolver nada
    solo, y el dueño todavía no sabe que su tarjeta falló."""
    ctx = armar_empresa()
    ctx.empresa.prueba_hasta = None
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=3)
    db.flush()
    fila = _suscripcion(db, ctx.empresa, estado=mp_debito.ACTIVO)
    fila.cobros_fallidos = 1
    db.flush()

    mandados = _correr_avisos(db, monkeypatch)
    assert [m for m in mandados if m[0] == ctx.empresa.id]


def test_al_que_paga_a_mano_se_le_sigue_avisando(db, armar_empresa, monkeypatch):
    """El control del control: si el silencio se aplicara a todos, este test
    se pondría en rojo y nadie recibiría un aviso de cobranza nunca más."""
    ctx = armar_empresa()
    ctx.empresa.prueba_hasta = None
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=3)
    db.flush()

    mandados = _correr_avisos(db, monkeypatch)
    assert [m for m in mandados if m[0] == ctx.empresa.id]
