"""Regresión del fix-016: PBKDF2 a 600.000 y el diagrama generado.

Dos cosas de la lista "cuando haya aire" de la auditoría (10.4), que ahora que
hay aire se hacen:

  · subir el costo del hash de contraseñas, con actualización transparente de
    las que ya estaban guardadas
  · regenerar el .dbml, que documentaba 17 tablas inexistentes y le faltaban 7
"""

import hashlib
import time

import pytest

from app.core import crypto
from app.core.crypto import (
    _ITERACIONES,
    hash_clave,
    hash_senuelo,
    necesita_rehash,
    verificar_clave,
)
from app.models import SuperAdmin, Usuario
from app.models.enums import RolUsuario

from .conftest import token_de


# ══════════════════════════════════════════════════════════════════════════
#  1. El costo del hash
# ══════════════════════════════════════════════════════════════════════════


def test_las_claves_nuevas_usan_600000_iteraciones():
    assert _ITERACIONES == 600_000
    almacenada = hash_clave("una-clave")
    algoritmo, iters, salt, _ = almacenada.split("$")
    assert algoritmo == "pbkdf2"
    assert int(iters) == 600_000
    assert len(salt) == 32          # 16 bytes de sal aleatoria


def test_una_clave_guardada_con_el_costo_viejo_sigue_entrando():
    """Lo más importante del fix: nadie se queda afuera de su cuenta.

    El número de iteraciones va DENTRO del hash guardado, así que verificar
    usa el que corresponda a cada uno. Si no fuera así, subir la constante
    dejaría a todos los usuarios existentes sin poder entrar.
    """
    salt = "a" * 32
    dk = hashlib.pbkdf2_hmac("sha256", b"clave-vieja", bytes.fromhex(salt), 390_000)
    vieja = f"pbkdf2$390000${salt}${dk.hex()}"

    assert verificar_clave("clave-vieja", vieja) is True
    assert verificar_clave("otra", vieja) is False


def test_un_hash_viejo_se_marca_para_actualizar():
    salt = "b" * 32
    dk = hashlib.pbkdf2_hmac("sha256", b"x", bytes.fromhex(salt), 390_000)
    assert necesita_rehash(f"pbkdf2$390000${salt}${dk.hex()}") is True


def test_un_hash_nuevo_no_se_toca():
    assert necesita_rehash(hash_clave("x")) is False


@pytest.mark.parametrize("basura", ["", "cualquier-cosa", "pbkdf2$abc$x$y", None])
def test_un_hash_ilegible_se_rehashea(basura):
    """Ante la duda, que quede prolijo."""
    assert necesita_rehash(basura) is True


def test_el_senuelo_cuesta_lo_mismo_que_un_hash_real():
    """La propiedad del fix-004 tiene que seguir en pie con el número nuevo."""
    _, iters, _, _ = hash_senuelo().split("$")
    assert int(iters) == _ITERACIONES


def test_hashear_no_se_volvio_absurdamente_caro():
    """370 ms está bien para un login. 3 segundos no."""
    arranque = time.perf_counter()
    hash_clave("medicion")
    tardanza = time.perf_counter() - arranque
    assert tardanza < 3.0, f"hashear tardó {tardanza:.2f}s"


# ══════════════════════════════════════════════════════════════════════════
#  2. El login actualiza al pasar
# ══════════════════════════════════════════════════════════════════════════


def _con_clave_vieja(db, usuario, clave: str) -> None:
    salt = "c" * 32
    dk = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(salt), 390_000)
    usuario.hash_clave = f"pbkdf2$390000${salt}${dk.hex()}"
    db.flush()


def test_al_entrar_con_una_clave_vieja_se_actualiza_sola(client, db, armar_empresa):
    """Subir el número no sirve si las claves viejas se quedan con el viejo."""
    ctx = armar_empresa()
    _con_clave_vieja(db, ctx.dueno, ctx.clave)
    assert necesita_rehash(ctx.dueno.hash_clave) is True

    r = client.post("/auth/login", json={"email": ctx.dueno.email, "clave": ctx.clave})

    assert r.status_code == 200
    db.refresh(ctx.dueno)
    assert necesita_rehash(ctx.dueno.hash_clave) is False
    # Y la clave sigue siendo la misma para el usuario.
    assert verificar_clave(ctx.clave, ctx.dueno.hash_clave) is True


def test_entrar_dos_veces_no_rehashea_de_nuevo(client, db, armar_empresa):
    ctx = armar_empresa()
    _con_clave_vieja(db, ctx.dueno, ctx.clave)

    client.post("/auth/login", json={"email": ctx.dueno.email, "clave": ctx.clave})
    db.refresh(ctx.dueno)
    primero = ctx.dueno.hash_clave

    client.post("/auth/login", json={"email": ctx.dueno.email, "clave": ctx.clave})
    db.refresh(ctx.dueno)
    assert ctx.dueno.hash_clave == primero


def test_una_clave_equivocada_no_rehashea_nada(client, db, armar_empresa):
    """Solo se rehashea después de verificar. Si no, cualquiera pisa el hash."""
    ctx = armar_empresa()
    _con_clave_vieja(db, ctx.dueno, ctx.clave)
    antes = ctx.dueno.hash_clave

    r = client.post(
        "/auth/login", json={"email": ctx.dueno.email, "clave": "no-es-la-clave"}
    )

    assert r.status_code == 401
    db.refresh(ctx.dueno)
    assert ctx.dueno.hash_clave == antes


def test_si_el_rehash_falla_el_usuario_entra_igual(client, db, armar_empresa, monkeypatch):
    """Actualizar el hash es una mejora, no una condición para entrar."""
    ctx = armar_empresa()
    _con_clave_vieja(db, ctx.dueno, ctx.clave)

    import app.routers.auth as auth_mod

    def explota(_clave):
        raise RuntimeError("se cayó el hasheo")

    monkeypatch.setattr(auth_mod, "hash_clave", explota)

    r = client.post("/auth/login", json={"email": ctx.dueno.email, "clave": ctx.clave})
    assert r.status_code == 200


def test_el_super_admin_tambien_se_actualiza(db, armar_empresa):
    from app.services.admin import autenticar_admin

    salt = "d" * 32
    dk = hashlib.pbkdf2_hmac("sha256", b"clave-admin", bytes.fromhex(salt), 390_000)
    sa = SuperAdmin(
        nombre="Admin 016",
        email=f"admin016-{salt[:6]}@turnos360.com",
        hash_clave=f"pbkdf2$390000${salt}${dk.hex()}",
    )
    db.add(sa)
    db.flush()

    assert autenticar_admin(db, sa.email, "clave-admin") is not None
    db.refresh(sa)
    assert necesita_rehash(sa.hash_clave) is False


def test_un_usuario_recien_creado_ya_nace_con_el_costo_nuevo(db, armar_empresa):
    ctx = armar_empresa()
    nuevo = Usuario(
        empresa_id=ctx.empresa.id,
        nombre="Nuevo",
        email=f"nuevo016-{ctx.empresa.slug}@example.com",
        hash_clave=hash_clave("clave1234"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(nuevo)
    db.flush()
    assert necesita_rehash(nuevo.hash_clave) is False


# ══════════════════════════════════════════════════════════════════════════
#  3. El diagrama no se puede volver a desactualizar
# ══════════════════════════════════════════════════════════════════════════


def _dbml_o_skip():
    """Devuelve el contenido del diagrama, o saltea con un motivo claro.

    Adentro del contenedor `docs/` puede no estar montado. Antes esto pasaba
    en verde comparando un archivo fantasma que el propio generador acababa de
    escribir en /docs — un test que se aprobaba a sí mismo. Mejor saltear y
    decir por qué.
    """
    from app.tools.generar_dbml import DESTINO

    if DESTINO is None:
        pytest.skip(
            "docs/ no se ve desde acá (¿contenedor sin la raíz del repo "
            "montada?). Este test corre desde el host o con el volumen de docs."
        )
    if not DESTINO.exists():
        pytest.fail(f"Falta {DESTINO} — corré: make dbml")
    return DESTINO.read_text(encoding="utf-8")


def test_el_diagrama_esta_al_dia():
    """Este test es el punto del fix.

    El .dbml anterior documentaba 17 tablas que no existían y le faltaban 7
    que sí. No porque nadie lo cuidara: porque estaba escrito a mano y no
    había forma de enterarse de que se había quedado atrás.

    Ahora se genera desde Base.metadata y este test compara el archivo contra
    lo que sale de los modelos. Agregás un modelo, te olvidás de `make dbml`,
    y la suite se pone roja el mismo día.
    """
    from app.tools.generar_dbml import generar

    en_disco = _dbml_o_skip()
    assert en_disco == generar(), (
        "docs/turnos360.dbml quedó desactualizado respecto de los modelos.\n"
        "Regeneralo con:  make dbml"
    )


def test_el_diagrama_sale_siempre_igual():
    """El generador tiene que ser determinista, no "casi siempre igual".

    `col.foreign_keys` es un SET. Cuando empresa_id pasó a participar en dos
    FKs —la suya a empresa.id y la compuesta (empresa_id, sucursal_id) hacia
    sucursal— tomar "el primero" empezó a devolver uno distinto según la
    corrida. Efecto: el test de arriba se ponía rojo día por medio sin que
    nadie tocara un modelo, que es la peor clase de test roto: el que enseña
    a ignorar los rojos.
    """
    from app.tools.generar_dbml import generar

    assert generar() == generar()


def test_el_diagrama_tiene_las_tablas_que_faltaban():
    """Las 7 que el diagrama escrito a mano no tenía."""
    contenido = _dbml_o_skip()
    for tabla in (
        "item_turno",
        "cupon_descuento",
        "wa_saldo",
        "wa_movimiento",
        "pago_suscripcion",
        "plan_abono",
        "medicion_antropometrica",
    ):
        assert f"Table {tabla} {{" in contenido, f"falta {tabla}"


def test_el_diagrama_no_inventa_tablas():
    """Y ninguna de las 17 que documentaba y no existían."""
    contenido = _dbml_o_skip()
    for fantasma in ("vehiculo", "orden_trabajo", "plan_saas", "saldo_puntos", "campania"):
        assert f"Table {fantasma} {{" not in contenido, f"{fantasma} no existe"


def test_el_diagrama_trae_los_tipos_reales_de_postgres():
    """Que diga jsonb y timestamp, no los genéricos de SQLAlchemy."""
    contenido = _dbml_o_skip()
    assert "jsonb" in contenido
    assert "timestamp with time zone" in contenido
    assert "bytea" in contenido


def test_generar_dos_veces_da_exactamente_lo_mismo():
    """Si no fuera determinístico, el test de arriba fallaría al azar."""
    from app.tools.generar_dbml import generar

    assert generar() == generar()


def test_el_modo_check_detecta_un_diagrama_viejo(monkeypatch, tmp_path):
    from app.tools import generar_dbml as mod

    falso = tmp_path / "viejo.dbml"
    falso.write_text("Table inventada {}\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DESTINO", falso)
    monkeypatch.setattr(mod.sys, "argv", ["x", "--check"])

    assert mod.main() == 1


def test_sin_carpeta_docs_avisa_en_vez_de_inventar_una_ruta(monkeypatch, capsys):
    """El bug del fix-016: escribía en /docs adentro del contenedor y decía OK.

    El archivo del repo nunca se tocaba y el comando salía en verde. Ahora, si
    no encuentra docs/, lo dice y sale con error.
    """
    from app.tools import generar_dbml as mod

    monkeypatch.setattr(mod, "DESTINO", None)
    monkeypatch.setattr(mod.sys, "argv", ["x"])

    assert mod.main() == 1
    assert "docs/" in capsys.readouterr().out


def test_el_modo_stdout_no_toca_ningun_archivo(monkeypatch, capsys):
    """Es el que usa `make dbml`: funciona monten lo que monten."""
    from app.tools import generar_dbml as mod

    monkeypatch.setattr(mod, "DESTINO", None)
    monkeypatch.setattr(mod.sys, "argv", ["x", "--stdout"])

    assert mod.main() == 0
    salida = capsys.readouterr().out
    assert "Table turno {" in salida
    assert salida == mod.generar()


def test_el_conteo_de_tablas_coincide_con_el_metadata():
    from app.db.base import Base
    contenido = _dbml_o_skip()
    declaradas = contenido.count("\nTable ")
    assert declaradas == len(Base.metadata.tables)


# ══════════════════════════════════════════════════════════════════════════
#  4. Control: nada de esto abrió una puerta
# ══════════════════════════════════════════════════════════════════════════


def test_el_login_sigue_sin_revelar_si_un_email_existe(client, db, armar_empresa):
    ctx = armar_empresa()
    inexistente = client.post(
        "/auth/login", json={"email": "no-existe-016@example.com", "clave": "x"}
    )
    existente = client.post(
        "/auth/login", json={"email": ctx.dueno.email, "clave": "clave-mala"}
    )
    assert inexistente.status_code == existente.status_code == 401
    assert inexistente.json()["detail"] == existente.json()["detail"]


def test_el_hash_no_viaja_en_ninguna_respuesta(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.get("/auth/me", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    assert "hash" not in r.text.lower()


def test_dos_hashes_de_la_misma_clave_son_distintos():
    """Sal aleatoria: dos usuarios con la misma clave no comparten hash."""
    assert hash_clave("misma-clave") != hash_clave("misma-clave")
    assert crypto.verificar_clave("misma-clave", hash_clave("misma-clave")) is True
