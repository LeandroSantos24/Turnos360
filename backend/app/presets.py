"""Presets de rubro: la configuración con la que nace una empresa nueva.

Vive en su propio módulo —y no adentro de `seeds.py`— porque `seeds_minimo`
lo necesita EN PRODUCCIÓN, y `seeds.py` arrastra Faker (26 MB) para generar
datos de mentira que en un servidor real no se usan nunca. Separarlos deja
la imagen de producción sin esa dependencia.

Son datos puros: no importan nada del proyecto ni tocan la base.
"""

PRESET_BARBERIA = {
    "terminologia": {"turno": "turno", "recurso": "barbero", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "preferencias_corte", "etiqueta": "Preferencias de corte", "tipo": "texto"},
        {"clave": "productos", "etiqueta": "Productos utilizados", "tipo": "texto"},
    ],
    "datos_sensibles": False,
}

PRESET_MEDICO = {
    "terminologia": {"turno": "turno", "recurso": "médico", "cliente": "paciente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": False, "ficha_clinica": True, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "obra_social", "etiqueta": "Obra social", "tipo": "texto"},
        {"clave": "nro_afiliado", "etiqueta": "N.º de afiliado", "tipo": "texto"},
    ],
    "datos_sensibles": True,
}

PRESET_NUTRICION = {
    "terminologia": {"turno": "consulta", "recurso": "profesional", "cliente": "paciente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": False, "ficha_clinica": True, "ordenes_trabajo": False},
    "campos_cliente": [],
    "datos_sensibles": True,
}

PRESET_UNAS = {
    "terminologia": {"turno": "turno", "recurso": "manicura", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "preferencias", "etiqueta": "Preferencias / alergias", "tipo": "texto"},
    ],
    "datos_sensibles": False,
}

PRESET_ESTETICA = {
    "terminologia": {"turno": "turno", "recurso": "profesional", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "tipo_piel", "etiqueta": "Tipo de piel", "tipo": "texto"},
        {"clave": "alergias", "etiqueta": "Alergias", "tipo": "texto"},
    ],
    "datos_sensibles": False,
}

PRESET_SPA = {
    "terminologia": {"turno": "sesión", "recurso": "profesional", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [],
    "datos_sensibles": False,
}
