"""La vista previa de «Mi página» usa los datos reales de la vidriera."""

from tests.conftest import token_de


# ── Vista previa de «Mi página» ───────────────────────────────────────

def test_la_previa_muestra_la_pagina_aunque_no_este_verificada(client, db, armar_empresa):
    ctx = armar_empresa("Estudio Previa")
    ctx.empresa.de_registro_publico = True
    ctx.dueno.email_verificado = False
    db.commit()

    # La pública todavía no se ve (candado anti-spam)…
    assert client.get(f"/publico/{ctx.empresa.slug}").status_code == 404
    # …pero el dueño ve la suya, con los mismos datos.
    r = client.get("/empresa/vidriera-previa", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    d = r.json()
    assert d["nombre"] == "Estudio Previa"
    assert d["slug"] == ctx.empresa.slug
    assert [s["nombre"] for s in d["servicios"]] == ["Corte"]


def test_la_previa_es_solo_del_dueno(client, armar_empresa):
    ctx = armar_empresa()
    assert client.get("/empresa/vidriera-previa", headers=token_de(ctx.profesional)).status_code == 403
