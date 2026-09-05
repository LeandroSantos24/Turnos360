"""Las imágenes que sube el negocio: que entren, y que no entre otra cosa.

POR QUÉ ESTE ARCHIVO ES DE SEGURIDAD Y NO DE FUNCIONALIDAD
Acá entra un archivo mandado por alguien de afuera y después se sirve por HTTP
desde nuestro dominio. Es la superficie más expuesta del sistema. Mirar la
extensión no sirve (se cambia) y el `content-type` tampoco (lo elige quien
sube); ni siquiera alcanza con leer los primeros bytes, porque existen archivos
POLÍGLOTOS —válidos como imagen y como HTML a la vez— que pasan cualquier
chequeo de cabecera.

La defensa es no guardar NUNCA el archivo que llegó: se abre con Pillow y se
escribe una imagen nueva a partir de los píxeles. Lo que no era píxel no
sobrevive. Estos tests fijan esa propiedad.
"""

import io

from PIL import Image

from .conftest import token_de


def _imagen(fmt="PNG", size=(80, 60), color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    buf.seek(0)
    return buf.read()


def _subir(client, ctx, contenido, nombre="foto.png", tipo="image/png", proposito=None):
    datos = {"proposito": proposito} if proposito else {}
    return client.post(
        "/subidas/imagen",
        headers=token_de(ctx.dueno),
        files={"archivo": (nombre, contenido, tipo)},
        data=datos,
    )


# ══════════════════════════════════════════════════════════════════════
#  Lo que tiene que funcionar
# ══════════════════════════════════════════════════════════════════════

def test_una_foto_normal_se_sube(client, db, armar_empresa, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    r = _subir(client, ctx, _imagen())
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith(f"/uploads/{ctx.empresa.id}/")
    assert url.endswith(".webp"), "Todo sale como webp, entre lo que entre."


def test_cada_negocio_guarda_en_su_carpeta(client, db, armar_empresa, tmp_path, monkeypatch):
    """Hace obvio de quién es cada archivo y deja borrar todo lo de una
    empresa de una sola vez si se da de baja."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    a = armar_empresa("Una")
    b = armar_empresa("Otra")
    db.commit()

    ua = _subir(client, a, _imagen()).json()["url"]
    ub = _subir(client, b, _imagen()).json()["url"]
    assert f"/{a.empresa.id}/" in ua
    assert f"/{b.empresa.id}/" in ub
    assert ua != ub


def test_una_foto_gigante_se_achica(client, db, armar_empresa, tmp_path, monkeypatch):
    """Una foto de celular son 12 megapíxeles y un avatar se muestra en 44."""
    from pathlib import Path

    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    r = _subir(client, ctx, _imagen(size=(3000, 2000)), proposito="avatar")
    assert r.status_code == 200, r.text

    guardada = Path(str(tmp_path)) / r.json()["url"].split("/uploads/")[1]
    with Image.open(guardada) as img:
        assert max(img.size) <= 512, f"Quedó en {img.size}"


def test_el_tamano_depende_de_para_que_es(client, db, armar_empresa, tmp_path, monkeypatch):
    """Un avatar no necesita lo mismo que una foto de la galería, que se abre
    a pantalla completa."""
    from pathlib import Path

    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    def lado(proposito):
        r = _subir(client, ctx, _imagen(size=(3000, 2000)), proposito=proposito)
        assert r.status_code == 200, r.text
        ruta = Path(str(tmp_path)) / r.json()["url"].split("/uploads/")[1]
        with Image.open(ruta) as img:
            return max(img.size)

    assert lado("avatar") < lado("galeria")


# ══════════════════════════════════════════════════════════════════════
#  Lo que NO tiene que entrar
# ══════════════════════════════════════════════════════════════════════

def test_un_archivo_que_no_es_imagen_se_rechaza(client, db, armar_empresa, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    r = _subir(client, ctx, b"#!/bin/sh\nrm -rf /\n", nombre="foto.png")
    assert r.status_code == 400, "Se llama .png y dice image/png, pero no lo es."


def test_un_html_disfrazado_de_imagen_se_rechaza(client, db, armar_empresa, tmp_path, monkeypatch):
    """El caso clásico: un archivo que el navegador podría interpretar como
    HTML si se sirviera. Con la extensión y el content-type de una imagen."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    r = _subir(client, ctx, b"<html><script>alert(1)</script></html>", nombre="x.jpg", tipo="image/jpeg")
    assert r.status_code == 400


def test_lo_que_no_era_pixel_no_sobrevive(client, db, armar_empresa, tmp_path, monkeypatch):
    """LA propiedad que hace segura toda esta ruta.

    Se sube una imagen VÁLIDA con una carga pegada al final —un políglota, que
    pasa cualquier chequeo de cabecera porque de verdad empieza como PNG—. Como
    el servidor no guarda el archivo que llegó sino que escribe uno nuevo desde
    los píxeles, la carga no puede estar en el resultado.
    """
    from pathlib import Path

    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    veneno = b"<script>alert('xss')</script>"
    r = _subir(client, ctx, _imagen() + veneno)
    assert r.status_code == 200, r.text

    guardada = Path(str(tmp_path)) / r.json()["url"].split("/uploads/")[1]
    assert veneno not in guardada.read_bytes(), (
        "La carga sobrevivió: el archivo se está guardando tal como llegó."
    )


def test_el_nombre_del_archivo_no_se_usa(client, db, armar_empresa, tmp_path, monkeypatch):
    """`../../etc/passwd` es un nombre de archivo válido. Si se concatenara a
    la ruta, se escribiría fuera de la carpeta. El nombre lo ponemos nosotros."""
    from pathlib import Path

    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    r = _subir(client, ctx, _imagen(), nombre="../../../etc/passwd.png")
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert ".." not in url
    assert "passwd" not in url

    guardada = Path(str(tmp_path)) / url.split("/uploads/")[1]
    assert guardada.resolve().is_relative_to(Path(str(tmp_path)).resolve())


def test_una_imagen_enorme_se_rechaza_por_peso(client, db, armar_empresa, tmp_path, monkeypatch):
    """Sin tope, un archivo gigante se carga entero en memoria antes de que
    nadie pueda rechazarlo, y con dos o tres alcanza para voltear el proceso."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    monkeypatch.setattr(settings, "upload_max_mb", 1)
    ctx = armar_empresa()
    db.commit()

    r = _subir(client, ctx, b"\x89PNG\r\n\x1a\n" + b"\0" * (2 * 1024 * 1024))
    assert r.status_code == 413


def test_un_proposito_inventado_se_rechaza(client, db, armar_empresa, tmp_path, monkeypatch):
    """El tamaño lo decide el servidor. Si el cliente pudiera mandar
    cualquiera, mandaría uno que guarde imágenes de 8000 px."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    assert _subir(client, ctx, _imagen(), proposito="gigante").status_code == 400


def test_un_archivo_vacio_se_rechaza(client, db, armar_empresa, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()
    assert _subir(client, ctx, b"").status_code == 400


# ══════════════════════════════════════════════════════════════════════
#  Quién puede subir
# ══════════════════════════════════════════════════════════════════════

def test_sin_sesion_no_se_puede_subir(client, tmp_path, monkeypatch):
    """Si no, cualquiera en internet usa el servidor de alojamiento gratis."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    r = client.post(
        "/subidas/imagen", files={"archivo": ("f.png", _imagen(), "image/png")}
    )
    assert r.status_code in (401, 403)


def test_un_profesional_no_sube_imagenes(client, db, armar_empresa, tmp_path, monkeypatch):
    """La imagen de la vidriera es del negocio: la cambia el dueño.

    Un profesional que pudiera subir podría cambiarle la portada al local, y
    además tendría alojamiento de archivos gratis en nuestro dominio.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    ctx = armar_empresa()
    db.commit()

    r = client.post(
        "/subidas/imagen",
        headers=token_de(ctx.profesional),
        files={"archivo": ("f.png", _imagen(), "image/png")},
    )
    assert r.status_code == 403, (
        "Un profesional pudo subir una imagen: falta el gate de dueño."
    )
