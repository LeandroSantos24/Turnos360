"""Regresión del fix-024: la clave del super-admin.

DOS AGUJEROS
────────────
1. En producción, el seed solo verificaba que SUPERADMIN_PASS no estuviera
   VACÍA. `SUPERADMIN_PASS=1234` pasaba sin chistar. Ese usuario controla el
   alta de todas las empresas, la pausa de cualquier negocio y las
   suscripciones del SaaS entero.

2. No había NINGUNA forma de cambiar esa clave. El panel no tiene pantalla
   para eso y el seed solo creaba el usuario si no existía. El día que se
   filtrara, había que arreglarlo a mano contra la base de producción.

Nota sobre el criterio: NO se exigen reglas de composición (una mayúscula, un
número, un símbolo). Están desaconsejadas por NIST SP 800-63B §5.1.1.2 desde
2017 porque no miden fuerza: empujan a `Password1!` y castigan a una frase
larga. Hay un test que lo fija, para que a nadie se le ocurra "endurecerlo"
agregándolas.
"""

import pytest

from app.core.claves import (
    LARGO_MINIMO,
    ClaveDebil,
    revisar_clave_superadmin,
)

EMAIL = "jefe@turnos360.com.ar"


# ══════════════════════════════════════════════════════════════════════════
#  1. Lo que NO puede pasar
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "clave",
    ["", "1234", "admin", "corta", "x" * (LARGO_MINIMO - 1)],
)
def test_una_clave_corta_no_pasa(clave):
    with pytest.raises(ClaveDebil):
        revisar_clave_superadmin(clave, EMAIL)


@pytest.mark.parametrize(
    "clave",
    [
        # Las dos que están escritas en seeds_minimo.py, en el repo PÚBLICO.
        "superadmin360",
        "admin",
        # Y las de cualquier lista.
        "password", "password123", "123456", "qwerty", "letmein",
        "changeme", "cambiar-en-produccion", "clave123", "turnos360",
    ],
)
def test_una_clave_conocida_no_pasa(clave):
    """La mayoría de los ataques no prueban combinaciones: prueban listas."""
    with pytest.raises(ClaveDebil):
        revisar_clave_superadmin(clave, EMAIL)


def test_la_clave_publicada_en_el_repo_se_rechaza_POR_SER_CONOCIDA():
    """No por corta. El motivo importa: si el mensaje dijera «es corta»,
    alguien pondría `superadmin360superadmin360` y estaría igual de mal."""
    with pytest.raises(ClaveDebil) as e:
        revisar_clave_superadmin("superadmin360", EMAIL)
    assert "público" in str(e.value) or "listas" in str(e.value)


@pytest.mark.parametrize(
    "clave",
    ["a" * 20, "abababababababababab", "121212121212121212"],
)
def test_una_clave_larga_pero_repetitiva_no_pasa(clave):
    """El largo solo sirve si hay algo adentro."""
    with pytest.raises(ClaveDebil):
        revisar_clave_superadmin(clave, EMAIL)


@pytest.mark.parametrize(
    "clave", ["abcdefghijklmnopqrst", "tsrqponmlkjihgfedcba"]
)
def test_una_secuencia_corrida_no_pasa(clave):
    with pytest.raises(ClaveDebil):
        revisar_clave_superadmin(clave, EMAIL)


@pytest.mark.parametrize(
    "clave",
    [
        "12345678901234567890",   # el que se me escapó
        "abcdefabcdefabcdefab" [:18],
        "Turno-2026Turno-2026",
        "xY9!xY9!xY9!xY9!xY9!",
    ],
)
def test_un_pedazo_corto_repetido_no_pasa(clave):
    """Este control lo agregué porque un test me lo encontró.

    `12345678901234567890` pasaba los otros tres: veinte caracteres (largo,
    bien), diez distintos (variedad, bien) y no es una cuesta corrida porque
    el 9 vuelve al 0 (secuencia, bien). Y es, obviamente, una de las peores
    claves que existen.

    Una clave hecha de un bloque repetido vale lo que vale el bloque, no lo
    que mide entera.
    """
    with pytest.raises(ClaveDebil):
        revisar_clave_superadmin(clave, EMAIL)


@pytest.mark.parametrize(
    "clave",
    [
        "jefe-una-clave-larga-igual",          # el usuario del email
        "clave-turnos360-larga-y-linda",       # el dominio
        "jefe@turnos360.com.ar-mas-cosas",     # el email entero
    ],
)
def test_una_clave_adivinable_desde_lo_publico_no_pasa(clave):
    """El email del admin y el dominio los sabe cualquiera que vea la página."""
    with pytest.raises(ClaveDebil):
        revisar_clave_superadmin(clave, EMAIL)


def test_el_error_dice_como_generar_una_buena():
    """Un error que solo dice «clave inválida» termina en alguien probando
    variantes hasta que pasa, que es lo contrario de lo que se busca."""
    with pytest.raises(ClaveDebil) as e:
        revisar_clave_superadmin("1234", EMAIL)
    assert "secrets" in str(e.value)


# ══════════════════════════════════════════════════════════════════════════
#  2. Lo que SÍ tiene que pasar
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "clave",
    [
        "kJ8x-Qm2Rt_9vLpZ4wN",                  # token_urlsafe típico
        "7fUq2Nn-vHs4LbXk9Tz1Rw",
        "vereda naranja tijera puente",         # una frase larga
        "MiClaveSuperSegura2026",
    ],
)
def test_una_clave_de_verdad_pasa(clave):
    revisar_clave_superadmin(clave, EMAIL)


def test_NO_se_exigen_reglas_de_composicion():
    """NIST 800-63B §5.1.1.2 las desaconseja desde 2017: no miden fuerza,
    miden obediencia. Este test existe para que nadie las agregue creyendo
    que endurece algo — empujan a `Password1!` y castigan a una frase larga.
    """
    # Solo minúsculas y espacios, sin números ni símbolos: tiene que pasar.
    revisar_clave_superadmin("vereda naranja tijera puente", EMAIL)
    # Solo letras, mezcla de mayúsculas: tiene que pasar.
    revisar_clave_superadmin("VeredaNaranjaTijeraPuente", EMAIL)


def test_sin_email_igual_valida_lo_demas():
    """El email es opcional: si no se pasa, los otros controles siguen."""
    revisar_clave_superadmin("kJ8x-Qm2Rt_9vLpZ4wN")
    with pytest.raises(ClaveDebil):
        revisar_clave_superadmin("1234")


@pytest.fixture()
def seed_en_el_test(db, monkeypatch):
    """Hace que el seed escriba en la sesión del test (que se revierte)."""
    from app import seeds_minimo
    from app.core.config import settings

    class SesionDelTest:
        def __call__(self):
            return self

        def __enter__(self):
            return db

        def __exit__(self, *_):
            return False

        # El seed usa db = SessionLocal() y db.close() al final.
        def close(self):
            db.flush()

        def __getattr__(self, nombre):
            return getattr(db, nombre)

    monkeypatch.setattr(seeds_minimo, "SessionLocal", SesionDelTest())
    monkeypatch.setattr(settings, "env", "dev")
    monkeypatch.setenv("SUPERADMIN_EMAIL", EMAIL)
    return seeds_minimo



# ══════════════════════════════════════════════════════════════════════════
#  3. El seed: en producción se planta, en desarrollo no molesta
# ══════════════════════════════════════════════════════════════════════════


def _correr_seed(seed, monkeypatch, *, clave, produccion, rotar=False):
    """Corre el seed SIEMPRE contra la sesión del test.

    La primera versión de este ayudante usaba el SessionLocal de verdad y el
    test de desarrollo escribía un super-admin en la base posta, que después
    rompía los tests de rotación. Lo encontré por eso: un test que ensucia la
    base es un test que va a hacer fallar a otro, tarde y lejos.
    """
    from app.core.config import settings

    monkeypatch.setenv("SUPERADMIN_PASS", clave)
    monkeypatch.setattr(settings, "env", "prod" if produccion else "dev")
    return seed.run(rotar_clave=rotar)


def test_en_produccion_una_clave_debil_frena_el_seed(monkeypatch, seed_en_el_test):
    with pytest.raises(SystemExit) as e:
        _correr_seed(seed_en_el_test, monkeypatch, clave="1234", produccion=True)
    assert "SUPERADMIN_PASS" in str(e.value)


def test_en_produccion_la_clave_del_repo_publico_frena_el_seed(
    monkeypatch, seed_en_el_test
):
    with pytest.raises(SystemExit) as e:
        _correr_seed(
            seed_en_el_test, monkeypatch, clave="superadmin360", produccion=True
        )
    assert "SUPERADMIN_PASS" in str(e.value)


def test_rotar_con_una_clave_debil_tambien_frena(monkeypatch, seed_en_el_test):
    """Rotar es el otro momento en que alguien elige esta clave. Si el control
    solo mirara producción, se podría rotar a `1234` desde cualquier lado."""
    with pytest.raises(SystemExit):
        _correr_seed(
            seed_en_el_test, monkeypatch, clave="1234", produccion=False, rotar=True
        )


def test_en_desarrollo_no_molesta(monkeypatch, seed_en_el_test):
    """En la máquina de trabajo la clave floja es un problema de nadie, y
    frenar ahí solo lograría que alguien apague el control."""
    _correr_seed(seed_en_el_test, monkeypatch, clave="clave1234", produccion=False)


# ══════════════════════════════════════════════════════════════════════════
#  4. Cada control tiene que estar haciendo SU trabajo
# ══════════════════════════════════════════════════════════════════════════
#
# Estos cuatro los agregué porque las mutaciones sobrevivieron: sacaba un
# control del código y los tests seguían en verde, porque otro control tapaba
# el caso. Un control que ningún test necesita es un control que alguien va a
# borrar en el próximo refactor creyendo que sobra.


def test_el_largo_minimo_rechaza_algo_que_los_otros_controles_dejarian_pasar():
    """`aB3-xY9z`: no está en ninguna lista, tiene ocho caracteres distintos,
    no es una cuesta corrida y no es un bloque repetido. Lo único que tiene
    de malo es que mide ocho."""
    corta = "aB3-xY9z"
    assert len(corta) < LARGO_MINIMO
    with pytest.raises(ClaveDebil, match="mínimo"):
        revisar_clave_superadmin(corta, EMAIL)


def test_la_variedad_rechaza_algo_que_los_otros_controles_dejarian_pasar():
    """`aaabaaabbaaabbbaaaab`: veinte caracteres, no conocida, no corrida y
    NO periódica. Lo único que tiene de malo es que son dos letras."""
    pobre = "aaabaaabbaaabbbaaaab"
    assert len(pobre) >= LARGO_MINIMO
    with pytest.raises(ClaveDebil, match="repite"):
        revisar_clave_superadmin(pobre, EMAIL)


# ══════════════════════════════════════════════════════════════════════════
#  5. La rotación, contra la base
# ══════════════════════════════════════════════════════════════════════════


CLAVE_A = "kJ8x-Qm2Rt_9vLpZ4wN"
CLAVE_B = "7fUq2Nn-vHs4LbXk9Tz1Rw"


def _hash_actual(db):
    from app.models import SuperAdmin

    sa = db.query(SuperAdmin).filter_by(email=EMAIL).first()
    return sa.hash_clave if sa else None


def test_el_seed_crea_el_superadmin_si_no_existe(db, monkeypatch, seed_en_el_test):
    from app.core.crypto import verificar_clave

    monkeypatch.setenv("SUPERADMIN_PASS", CLAVE_A)
    seed_en_el_test.run()

    assert verificar_clave(CLAVE_A, _hash_actual(db)) is True


def test_SIN_la_bandera_no_le_pisa_la_clave_al_que_ya_existe(
    db, monkeypatch, seed_en_el_test
):
    """La garantía que hace que este seed se pueda correr sin miedo.

    Es idempotente por diseño: se corre en cada deploy para dar de alta rubros
    nuevos. Si además cambiara la clave del super-admin, un deploy rutinario
    dejaría a alguien afuera de su propio panel.
    """
    from app.core.crypto import verificar_clave

    monkeypatch.setenv("SUPERADMIN_PASS", CLAVE_A)
    seed_en_el_test.run()

    monkeypatch.setenv("SUPERADMIN_PASS", CLAVE_B)
    seed_en_el_test.run()                      # sin --rotar-clave

    hash_final = _hash_actual(db)
    assert verificar_clave(CLAVE_A, hash_final) is True, "le pisó la clave sin pedirlo"
    assert verificar_clave(CLAVE_B, hash_final) is False


def test_CON_la_bandera_la_clave_vieja_deja_de_servir(
    db, monkeypatch, seed_en_el_test
):
    """El punto de la rotación: antes no había ninguna forma de cambiarla."""
    from app.core.crypto import verificar_clave

    monkeypatch.setenv("SUPERADMIN_PASS", CLAVE_A)
    seed_en_el_test.run()

    monkeypatch.setenv("SUPERADMIN_PASS", CLAVE_B)
    seed_en_el_test.run(rotar_clave=True)

    hash_final = _hash_actual(db)
    assert verificar_clave(CLAVE_B, hash_final) is True, "no rotó nada"
    assert verificar_clave(CLAVE_A, hash_final) is False, "la vieja todavía entra"


def test_el_seed_deja_los_rubros_cargados(db, monkeypatch, seed_en_el_test):
    """Es la otra mitad de para qué existe: sin rubros no se puede crear ni
    una empresa, porque crear_empresa exige un rubro_id que exista."""
    from app.models import Rubro

    monkeypatch.setenv("SUPERADMIN_PASS", CLAVE_A)
    seed_en_el_test.run()

    codigos = {r.codigo for r in db.query(Rubro).all()}
    assert {"barberia", "medico", "nutricion"} <= codigos
