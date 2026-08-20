"""Regresión del fix-004 (auditoría de agosto 2026).

Cada test de acá corresponde a un hallazgo concreto del informe. Si alguno se
pone en rojo, el agujero volvió.
"""

from fastapi import Request

from app.core.crypto import hash_senuelo, verificar_clave
from app.core.rate_limit import ip_del_cliente
from app.models.enums import TipoMovimiento
from app.models.finanzas import CategoriaFinanciera
from app.routers.admin import _datos_del_pedido, _ip_real

from .conftest import token_de


def _request_falso(headers: dict, client_host: str = "172.18.0.5") -> Request:
    """Arma un Request de Starlette a mano, sin levantar el servidor."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/admin/login",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 12345),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


# ══════════════════════════════════════════════════════════════════════
# Hallazgo 3.1 — CRÍTICO: el rate limit se salteaba con X-Forwarded-For
# ══════════════════════════════════════════════════════════════════════

def test_la_clave_del_rate_limit_no_sale_de_x_forwarded_for():
    """X-Forwarded-For lo elige el cliente: no puede decidir su propio cupo.

    Nginx usa $proxy_add_x_forwarded_for, que AGREGA al final. Si el limitador
    mirara el primer valor, cada request podría inventarse una IP distinta y
    no llegar nunca a 429.
    """
    req = _request_falso(
        {"x-forwarded-for": "1.2.3.4, 172.18.0.1", "x-real-ip": "190.55.1.1"},
        client_host="172.18.0.1",
    )
    assert ip_del_cliente(req) == "190.55.1.1"


def test_la_clave_del_rate_limit_ignora_un_x_forwarded_for_inventado():
    req = _request_falso({"x-forwarded-for": "9.9.9.9"}, client_host="172.18.0.1")
    assert ip_del_cliente(req) != "9.9.9.9"


def test_sin_proxy_se_usa_la_ip_de_la_conexion():
    """En desarrollo no hay Nginx: el header no existe y vale la IP real."""
    req = _request_falso({}, client_host="127.0.0.1")
    assert ip_del_cliente(req) == "127.0.0.1"


# ══════════════════════════════════════════════════════════════════════
# Hallazgo 3.5 — ALTO: el mail de alerta se falsificaba desde internet
# ══════════════════════════════════════════════════════════════════════

def test_el_user_agent_no_puede_inyectar_html_en_el_mail_de_alerta():
    """El aviso de acceso es el único registro del sistema: no es escribible."""
    req = _request_falso(
        {
            "user-agent": '</div><p>Falsa alarma: ignoralo</p>',
            "referer": '<a href="https://evil.tld">Ingresá acá</a>',
            "x-real-ip": "190.55.1.1",
        }
    )
    datos = _datos_del_pedido(req)
    assert "<p>" not in datos["agente"]
    assert "&lt;" in datos["agente"]
    assert "<a href" not in datos["vino_de"]


def test_una_ip_que_no_es_ip_no_llega_al_mail_ni_al_geolocalizador():
    """El valor viaja al asunto y a la URL del servicio de ubicación."""
    req = _request_falso({"x-real-ip": "no-soy-una-ip/../../etc/passwd"})
    assert _ip_real(req) == "desconocida"


def test_una_ip_valida_pasa_intacta():
    req = _request_falso({"x-real-ip": "190.55.1.1"})
    assert _ip_real(req) == "190.55.1.1"


# ══════════════════════════════════════════════════════════════════════
# Hallazgo 3.6 — MEDIO: se enumeraba el email del super-admin por timing
# ══════════════════════════════════════════════════════════════════════

def test_el_senuelo_del_login_admin_cuesta_lo_mismo_que_un_hash_real():
    """El señuelo viejo usaba 1 iteración contra 390.000: se medía con curl."""
    senuelo = hash_senuelo()
    iteraciones = int(senuelo.split("$")[1])
    assert iteraciones >= 100_000, (
        f"El señuelo usa {iteraciones} iteraciones: un email inexistente "
        "responde mucho más rápido que uno real y se puede enumerar."
    )
    # Y tiene que fallar igual que cualquier clave incorrecta.
    assert verificar_clave("lo-que-sea", senuelo) is False


# ══════════════════════════════════════════════════════════════════════
# Hallazgo 3.7 — MEDIO: fuga entre empresas por metodo_pago_id
# ══════════════════════════════════════════════════════════════════════

def test_no_se_puede_cargar_un_gasto_con_un_metodo_de_otra_empresa(client, db, armar_empresa):
    a = armar_empresa("Empresa A")
    b = armar_empresa("Empresa B")
    db.commit()

    r = client.post(
        "/gastos",
        headers=token_de(a.dueno),
        json={"concepto": "Sonda", "monto": 1, "metodo_pago_id": b.metodo.id},
    )
    assert r.status_code == 400, (
        "Se aceptó un método de pago de otra empresa: eso deja el libro mayor "
        "apuntando a otro tenant y esquiva el cálculo de comisión."
    )


def test_no_se_puede_cargar_un_gasto_con_una_categoria_de_otra_empresa(
    client, db, armar_empresa
):
    a = armar_empresa("Empresa A")
    b = armar_empresa("Empresa B")
    cat_b = CategoriaFinanciera(
        empresa_id=b.empresa.id, nombre="Alquiler", tipo=TipoMovimiento.EGRESO
    )
    db.add(cat_b)
    db.commit()

    r = client.post(
        "/gastos",
        headers=token_de(a.dueno),
        json={"concepto": "Sonda", "monto": 1, "categoria_id": cat_b.id},
    )
    assert r.status_code == 400


def test_el_gasto_con_un_metodo_propio_sigue_funcionando(client, db, armar_empresa):
    """La validación no puede romper el camino normal."""
    a = armar_empresa("Empresa A")
    db.commit()

    r = client.post(
        "/gastos",
        headers=token_de(a.dueno),
        json={"concepto": "Café", "monto": 1500, "metodo_pago_id": a.metodo.id},
    )
    assert r.status_code == 201


def test_el_listado_de_movimientos_no_revela_metodos_de_otra_empresa(
    client, db, armar_empresa
):
    """Aunque quedara un id ajeno guardado, el nombre no se resuelve."""
    a = armar_empresa("Empresa A")
    b = armar_empresa("Empresa B")
    b.metodo.nombre = "Cuenta secreta de B"
    db.commit()

    # Gasto legítimo de A, y después forzamos el id ajeno en la base para
    # simular un registro viejo anterior al arreglo.
    r = client.post(
        "/gastos",
        headers=token_de(a.dueno),
        json={"concepto": "Algo", "monto": 100, "metodo_pago_id": a.metodo.id},
    )
    assert r.status_code == 201
    mov_id = r.json()["id"]

    from app.models.finanzas import MovimientoFinanciero

    mov = db.get(MovimientoFinanciero, mov_id)
    mov.metodo_pago_id = b.metodo.id
    db.commit()

    r = client.get("/movimientos", headers=token_de(a.dueno))
    assert r.status_code == 200
    cuerpo = r.text
    assert "Cuenta secreta de B" not in cuerpo, (
        "El listado de movimientos filtró el nombre de un método de otra empresa."
    )


# ══════════════════════════════════════════════════════════════════════
# Hallazgo 3.8 — ALTO: "enviarme una prueba" era un relay de mail abierto
# ══════════════════════════════════════════════════════════════════════

def test_la_prueba_de_campana_ignora_el_destino_que_manden(
    client, db, armar_empresa, monkeypatch
):
    """El destino ya no se elige: va al email del usuario autenticado."""
    a = armar_empresa("Empresa A")
    db.commit()

    capturado = {}

    class TareaFalsa:
        @staticmethod
        def delay(empresa_id, tipo, destino):
            capturado["destino"] = destino

    import app.tasks.emails as emails_mod

    monkeypatch.setattr(emails_mod, "enviar_prueba_campana", TareaFalsa, raising=False)

    r = client.post(
        "/empresa/automatizaciones/probar",
        headers=token_de(a.dueno),
        params={"tipo": "cumple", "destino": "victima@ajeno.com"},
    )
    assert r.status_code == 200
    assert capturado.get("destino") == a.dueno.email, (
        "La prueba se mandó a un destinatario arbitrario: eso es un relay de "
        "mail abierto con la marca y la cuota de envíos de Turnos360."
    )


# ══════════════════════════════════════════════════════════════════════
# Rentabilidad de planes: era visible para cualquier rol
# ══════════════════════════════════════════════════════════════════════

def test_el_profesional_no_ve_la_rentabilidad_de_los_planes(client, db, armar_empresa):
    a = armar_empresa("Empresa A")
    db.commit()

    r = client.get("/membresias/estadisticas", headers=token_de(a.profesional))
    assert r.status_code == 403, (
        "Un profesional pudo ver el precio efectivo por corte y el margen de "
        "cada plan de abono."
    )


def test_el_dueno_si_ve_la_rentabilidad_de_los_planes(client, db, armar_empresa):
    a = armar_empresa("Empresa A")
    db.commit()

    r = client.get("/membresias/estadisticas", headers=token_de(a.dueno))
    assert r.status_code == 200
