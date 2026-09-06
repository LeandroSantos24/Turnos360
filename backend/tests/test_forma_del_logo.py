"""La forma del logo dice lo mismo en los cuatro lugares donde se decide.

EL BUG QUE ORIGINÓ ESTE ARCHIVO
───────────────────────────────
Leandro subió el logo de su barbería y le salió recortado en círculo aunque
tenía elegido «Cuadrado». No era un bug: eran tres lugares decidiendo la forma
por su cuenta, sin preguntarse nada entre ellos.

  · el recorte al subir       → círculo cableado en components/subir-imagen.tsx
  · la vista previa del panel → miraba `logo_forma` (el único que acertaba)
  · la página pública real    → cuadrado redondeado cableado, y `object-cover`

O sea: encuadraba dentro de un círculo, la previa le mostraba un cuadrado, y
su cliente veía un tercer recorte. Y el cuarto lugar es este, el backend, que
es el que puede rechazar el guardado entero con un 422 si el frontend ofrece
una forma que acá no está.

QUÉ PUEDE Y QUÉ NO PUEDE VERIFICAR ESTE ARCHIVO
───────────────────────────────────────────────
Puede verificar que las LISTAS coincidan y que el backend acepte y devuelva
cada forma. No puede verificar cómo se dibujan los píxeles: eso es CSS y vive
en TypeScript. Lo que sí hace es exigir que los tres archivos del frontend
lean la geometría del ÚNICO lugar donde está definida (`formaDelLogo`), en vez
de calcularla cada uno — que es exactamente lo que fallaba.
"""

import pathlib
import re

import pytest

from app.schemas.empresa import TemaVidriera
from tests.conftest import token_de

RAIZ = pathlib.Path(__file__).resolve().parents[2]
TEMA = RAIZ / "frontend/src/lib/tema-vidriera.ts"


def _formas_del_backend() -> set[str]:
    """Los valores que acepta el Literal de `logo_forma`."""
    import typing

    campo = TemaVidriera.model_fields["logo_forma"]
    return set(typing.get_args(campo.annotation))


def _saltear_sin_frontend(ruta: pathlib.Path) -> None:
    if not ruta.exists():
        pytest.skip(
            f"No encuentro {ruta} (es lo normal adentro del contenedor del "
            "backend). Este chequeo corre en tu máquina con `pytest` desde la "
            "raíz del repo."
        )


# ══════════════════════════════════════════════════════════════════════
#  1. Las listas coinciden
# ══════════════════════════════════════════════════════════════════════

def test_las_formas_del_frontend_y_del_backend_son_las_mismas():
    """Si el frontend ofrece una forma que el backend no acepta, guardar «Mi
    página» devuelve un 422 hablando de un campo que el dueño ni tocó."""
    _saltear_sin_frontend(TEMA)

    m = re.search(r"export type LogoForma =([^;]+);", TEMA.read_text(encoding="utf-8"))
    assert m, "No encontré `export type LogoForma` en tema-vidriera.ts."
    del_front = set(re.findall(r'"([a-z]+)"', m.group(1)))

    assert del_front == _formas_del_backend(), (
        f"El frontend ofrece {sorted(del_front)} y el backend acepta "
        f"{sorted(_formas_del_backend())}. La que sobre de un lado rompe el "
        "guardado del otro."
    )


def test_cada_forma_tiene_su_geometria_definida():
    """`FORMAS_DE_LOGO` tiene que cubrir TODAS las formas del tipo.

    TypeScript ya lo exige con `Record<LogoForma, …>`, pero el tipo se escribe
    en un lado y el mapa en otro: este test es el que falla en la suite del
    backend si alguien agrega una forma y se olvida de la geometría.
    """
    _saltear_sin_frontend(TEMA)
    texto = TEMA.read_text(encoding="utf-8")

    bloque = re.search(r"FORMAS_DE_LOGO: Record<.*?> = \{(.*?)\n\};", texto, re.S)
    assert bloque, "No encontré el mapa FORMAS_DE_LOGO."
    definidas = set(re.findall(r"^  ([a-z]+): \{", bloque.group(1), re.M))

    assert definidas == _formas_del_backend(), (
        f"FORMAS_DE_LOGO define {sorted(definidas)} y las formas válidas son "
        f"{sorted(_formas_del_backend())}."
    )


# ══════════════════════════════════════════════════════════════════════
#  2. Nadie vuelve a calcular la forma por su cuenta
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "archivo",
    [
        "frontend/src/app/(public)/[slug]/page.tsx",
        "frontend/src/app/(panel)/mi-pagina/vista-previa.tsx",
        "frontend/src/app/(panel)/mi-pagina/panel-look.tsx",
    ],
)
def test_los_tres_leen_la_geometria_del_mismo_lugar(archivo):
    """LA regla que evita que esto vuelva a pasar.

    Cada uno de estos tres archivos dibuja el logo en algún lado —la página
    real, la previa del celular, la previa del editor— y los tres tienen que
    sacar el radio y el `object-fit` de `formaDelLogo`. El día que uno vuelva
    a escribir `borderRadius: "999px"` a mano, las previas dejan de coincidir
    con la página y nadie se entera hasta que un cliente lo ve.
    """
    ruta = RAIZ / archivo
    _saltear_sin_frontend(ruta)
    texto = ruta.read_text(encoding="utf-8")

    assert "formaDelLogo" in texto, (
        f"{archivo} dibuja el logo pero no usa `formaDelLogo`. La geometría "
        "vive en lib/tema-vidriera.ts: si este archivo la calcula por su "
        "cuenta, vuelve a haber dos respuestas para la misma pregunta."
    )


def test_el_recorte_al_subir_recibe_la_forma_elegida():
    """El recorte tiene que dar EXACTAMENTE la figura que se eligió.

    Es el bug que vio Leandro: `subir-imagen.tsx` tenía el círculo cableado
    para el logo, así que encuadraba en redondo y después le aparecían las
    esquinas. El componente ahora acepta una forma; lo que este test cuida es
    que el panel se la PASE — un componente que acepta un parámetro que nadie
    manda es lo mismo que no tenerlo.
    """
    ruta = RAIZ / "frontend/src/app/(panel)/mi-pagina/panel-look.tsx"
    _saltear_sin_frontend(ruta)
    texto = ruta.read_text(encoding="utf-8")

    subida = re.search(r'<SubirImagen\s+proposito="logo"(.*?)/>', texto, re.S)
    assert subida, "No encontré el <SubirImagen proposito=\"logo\"> del panel."
    assert "forma={" in subida.group(1), (
        "El logo se sube sin pasarle la forma: vuelve al círculo cableado, "
        "que es el bug original."
    )


# ══════════════════════════════════════════════════════════════════════
#  3. El backend guarda y devuelve cada forma
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("forma", sorted(_formas_del_backend()))
def test_se_puede_guardar_y_recuperar_cada_forma(client, db, armar_empresa, forma):
    """Sin esto, una forma nueva se ofrece en el panel, se guarda con un 200 y
    vuelve convertida en otra — el dueño elige y no pasa nada."""
    ctx = armar_empresa()
    db.commit()

    r = client.put(
        "/empresa/landing",
        headers=token_de(ctx.dueno),
        json={"tema": {"logo_forma": forma}},
    )
    assert r.status_code == 200, r.text

    vuelta = client.get("/empresa/landing", headers=token_de(ctx.dueno)).json()
    assert vuelta["tema"]["logo_forma"] == forma


def test_una_forma_inventada_se_rechaza(client, db, armar_empresa):
    """El control del control: si el schema aceptara cualquier string, los
    tests de arriba pasarían sin que el Literal exista."""
    ctx = armar_empresa()
    db.commit()

    r = client.put(
        "/empresa/landing",
        headers=token_de(ctx.dueno),
        json={"tema": {"logo_forma": "triangulo"}},
    )
    assert r.status_code == 422
