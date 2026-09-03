"""Presets de rubro: la configuración con la que nace una empresa nueva.

Vive en su propio módulo —y no adentro de `seeds.py`— porque `seeds_minimo` lo
necesita EN PRODUCCIÓN, y `seeds.py` arrastra Faker (26 MB) para generar datos
de mentira que en un servidor real no se usan nunca. Separarlos deja la imagen
de producción sin esa dependencia.

Son datos puros: no importan nada del proyecto ni tocan la base.

QUÉ HACE UN PRESET, Y QUÉ CAMBIÓ
────────────────────────────────
Antes traían solo terminología, módulos y campos de ficha. El negocio entraba
con la aplicación bien nombrada… y absolutamente vacía: sin servicios, sin
precios y con una agenda de una sola columna. El primer paso real seguía siendo
una pantalla en blanco.

Ahora cada preset trae además `servicios`: tres a cinco de los que ese rubro
usa siempre, con su duración, un precio de referencia y su carril de agenda.
Son un PUNTO DE PARTIDA para editar, no una imposición — se cambian, se borran
y se agregan los propios desde Servicios. Pero la diferencia entre "cargá tus
servicios" y "acá están los cinco de siempre, corregí los precios" es la
diferencia entre abandonar en el primer paso y tener la agenda andando en cinco
minutos.

LOS PRECIOS SON REFERENCIA Y ENVEJECEN
──────────────────────────────────────
Son valores de mercado argentino a mediados de 2026, redondeados. Con la
inflación de acá quedan viejos rápido, y está bien: el dueño los corrige una
vez, al principio, mirando su propia lista. Lo que no envejece es la duración y
el carril, que es la parte difícil de adivinar para alguien que nunca usó un
sistema de turnos.

EL CARRIL (`grupo`) ES LO QUE HACE FUNCIONAR LA AGENDA EN PARALELO
──────────────────────────────────────────────────────────────────
Dos servicios del MISMO carril no pueden pasar a la misma hora con el mismo
profesional; dos de carriles distintos, sí. Es lo que permite que un corte y
una tintura convivan en la misma silla. `None` significa que el servicio ocupa
al profesional entero, que es lo correcto para una consulta médica o una sesión
de kinesiología: ahí no hay nada que hacer en paralelo.
"""

# ── Barbería y peluquería ────────────────────────────────────────────────
PRESET_BARBERIA = {
    "terminologia": {"turno": "turno", "recurso": "barbero", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "preferencias_corte", "etiqueta": "Preferencias de corte", "tipo": "texto"},
        {"clave": "productos", "etiqueta": "Productos utilizados", "tipo": "texto"},
    ],
    "datos_sensibles": False,
    # El caso que hizo que existieran los carriles: mientras uno espera que le
    # agarre el color, el barbero atiende una barba. Tres carriles distintos.
    "servicios": [
        {"nombre": "Corte", "duracion_min": 30, "precio": 9000, "grupo": "corte", "paso_turno_min": 20},
        {"nombre": "Corte y barba", "duracion_min": 45, "precio": 13000, "grupo": "corte", "paso_turno_min": 20},
        {"nombre": "Barba", "duracion_min": 20, "precio": 6000, "grupo": "barba", "paso_turno_min": 20},
        {"nombre": "Color", "duracion_min": 90, "precio": 22000, "grupo": "tintura", "paso_turno_min": 60},
    ],
}

# ── Uñas ─────────────────────────────────────────────────────────────────
PRESET_UNAS = {
    "terminologia": {"turno": "turno", "recurso": "manicura", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "preferencias", "etiqueta": "Preferencias / alergias", "tipo": "texto"},
    ],
    "datos_sensibles": False,
    # Manos y pies van en carriles distintos porque se hacen juntos: mientras
    # secan las manos, se empiezan los pies.
    "servicios": [
        {"nombre": "Semipermanente", "duracion_min": 60, "precio": 12000, "grupo": "manos", "paso_turno_min": 30},
        {"nombre": "Kapping / esculpidas", "duracion_min": 120, "precio": 22000, "grupo": "manos", "paso_turno_min": 30},
        {"nombre": "Retiro", "duracion_min": 30, "precio": 5000, "grupo": "manos", "paso_turno_min": 30},
        {"nombre": "Pedicuría", "duracion_min": 60, "precio": 13000, "grupo": "pies", "paso_turno_min": 30},
    ],
}

# ── Estética ─────────────────────────────────────────────────────────────
PRESET_ESTETICA = {
    "terminologia": {"turno": "turno", "recurso": "profesional", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "tipo_piel", "etiqueta": "Tipo de piel", "tipo": "texto"},
        {"clave": "alergias", "etiqueta": "Alergias", "tipo": "texto"},
    ],
    "datos_sensibles": False,
    "servicios": [
        {"nombre": "Limpieza facial profunda", "duracion_min": 60, "precio": 18000, "grupo": "faciales", "paso_turno_min": 30},
        {"nombre": "Depilación definitiva (sesión)", "duracion_min": 30, "precio": 15000, "grupo": "corporales", "paso_turno_min": 30},
        {"nombre": "Perfilado de cejas", "duracion_min": 30, "precio": 7000, "grupo": "cejas", "paso_turno_min": 15},
        {"nombre": "Lifting de pestañas", "duracion_min": 60, "precio": 16000, "grupo": "pestanas", "paso_turno_min": 30},
    ],
}

# ── Spa y masajes ────────────────────────────────────────────────────────
PRESET_SPA = {
    "terminologia": {"turno": "sesión", "recurso": "profesional", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "preferencias", "etiqueta": "Preferencias / zonas a evitar", "tipo": "texto"},
        {"clave": "contraindicaciones", "etiqueta": "Contraindicaciones", "tipo": "texto"},
    ],
    "datos_sensibles": False,
    # Sin carriles paralelos: un masaje ocupa al masajista y a la camilla. El
    # `grupo` está igual para que la agenda separe masajes de faciales, que en
    # un spa con dos profesionales sí pasan a la vez.
    "servicios": [
        {"nombre": "Masaje descontracturante", "duracion_min": 60, "precio": 20000, "grupo": "masajes", "paso_turno_min": 30},
        {"nombre": "Masaje relajante", "duracion_min": 60, "precio": 18000, "grupo": "masajes", "paso_turno_min": 30},
        {"nombre": "Drenaje linfático", "duracion_min": 60, "precio": 22000, "grupo": "masajes", "paso_turno_min": 30},
        {"nombre": "Ritual facial", "duracion_min": 75, "precio": 25000, "grupo": "faciales", "paso_turno_min": 30},
    ],
}

# ── Consultorio médico ───────────────────────────────────────────────────
PRESET_MEDICO = {
    "terminologia": {"turno": "turno", "recurso": "médico", "cliente": "paciente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": False, "ficha_clinica": True, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "obra_social", "etiqueta": "Obra social", "tipo": "texto"},
        {"clave": "nro_afiliado", "etiqueta": "N.º de afiliado", "tipo": "texto"},
    ],
    "datos_sensibles": True,
    # `grupo: None` a propósito. Una consulta ocupa al médico entero: no hay
    # nada que hacer en paralelo, y ofrecer dos turnos a la misma hora sería
    # sobreturno encubierto.
    "servicios": [
        {"nombre": "Consulta", "duracion_min": 30, "precio": 25000, "grupo": None, "paso_turno_min": 30},
        {"nombre": "Control", "duracion_min": 20, "precio": 18000, "grupo": None, "paso_turno_min": 20},
        {"nombre": "Primera consulta", "duracion_min": 45, "precio": 35000, "grupo": None, "paso_turno_min": 45},
    ],
}

# ── Nutrición ────────────────────────────────────────────────────────────
PRESET_NUTRICION = {
    "terminologia": {"turno": "consulta", "recurso": "profesional", "cliente": "paciente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": False, "ficha_clinica": True, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "objetivo", "etiqueta": "Objetivo de la consulta", "tipo": "texto"},
        {"clave": "obra_social", "etiqueta": "Obra social", "tipo": "texto"},
    ],
    "datos_sensibles": True,
    "servicios": [
        {"nombre": "Primera consulta", "duracion_min": 60, "precio": 30000, "grupo": None, "paso_turno_min": 60},
        {"nombre": "Consulta de seguimiento", "duracion_min": 30, "precio": 20000, "grupo": None, "paso_turno_min": 30},
        {"nombre": "Antropometría", "duracion_min": 30, "precio": 18000, "grupo": None, "paso_turno_min": 30},
    ],
}

# ── Kinesiología ─────────────────────────────────────────────────────────
PRESET_KINESIOLOGIA = {
    "terminologia": {"turno": "sesión", "recurso": "kinesiólogo", "cliente": "paciente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": False, "ficha_clinica": True, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "diagnostico_derivacion", "etiqueta": "Diagnóstico / derivación", "tipo": "texto"},
        {"clave": "obra_social", "etiqueta": "Obra social", "tipo": "texto"},
        {"clave": "sesiones_autorizadas", "etiqueta": "Sesiones autorizadas", "tipo": "numero"},
    ],
    "datos_sensibles": True,
    # El rubro donde las MEMBRESÍAS son el modelo de negocio, no un extra: casi
    # nadie compra una sesión suelta, se compran bonos de diez.
    "servicios": [
        {"nombre": "Sesión de kinesiología", "duracion_min": 45, "precio": 18000, "grupo": None, "paso_turno_min": 45},
        {"nombre": "Primera evaluación", "duracion_min": 60, "precio": 25000, "grupo": None, "paso_turno_min": 60},
        {"nombre": "Terapia manual", "duracion_min": 45, "precio": 22000, "grupo": None, "paso_turno_min": 45},
    ],
}

# ── Psicología ───────────────────────────────────────────────────────────
PRESET_PSICOLOGIA = {
    "terminologia": {"turno": "sesión", "recurso": "profesional", "cliente": "paciente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": False, "ficha_clinica": True, "ordenes_trabajo": False},
    # Deliberadamente pocos campos y ninguno clínico. La ficha de un paciente
    # de psicología es lo más sensible que puede pasar por este sistema, y un
    # campo prellenado es una invitación a escribir ahí. Que cada profesional
    # decida qué guarda y qué no.
    "campos_cliente": [
        {"clave": "modalidad", "etiqueta": "Modalidad (presencial / online)", "tipo": "texto"},
    ],
    "datos_sensibles": True,
    "servicios": [
        {"nombre": "Sesión", "duracion_min": 50, "precio": 25000, "grupo": None, "paso_turno_min": 60},
        {"nombre": "Primera entrevista", "duracion_min": 60, "precio": 30000, "grupo": None, "paso_turno_min": 60},
    ],
}

# ── Tatuajes y piercings ─────────────────────────────────────────────────
PRESET_TATUAJES = {
    "terminologia": {"turno": "sesión", "recurso": "artista", "cliente": "cliente"},
    "tipo_turno_default": "simple",
    "modulos": {"gift_cards": True, "ficha_clinica": False, "ordenes_trabajo": False},
    "campos_cliente": [
        {"clave": "idea", "etiqueta": "Idea / referencia", "tipo": "texto"},
        {"clave": "zona", "etiqueta": "Zona del cuerpo", "tipo": "texto"},
        {"clave": "alergias", "etiqueta": "Alergias", "tipo": "texto"},
    ],
    "datos_sensibles": False,
    # El rubro que más usa la SEÑA: una sesión de cuatro horas que se cae sin
    # aviso es medio día de trabajo perdido y no se recupera.
    "servicios": [
        {"nombre": "Consulta y presupuesto", "duracion_min": 30, "precio": 0, "grupo": "consulta", "paso_turno_min": 30},
        {"nombre": "Sesión de tatuaje", "duracion_min": 180, "precio": 60000, "grupo": "tatuaje", "paso_turno_min": 60},
        {"nombre": "Retoque", "duracion_min": 60, "precio": 15000, "grupo": "tatuaje", "paso_turno_min": 30},
        {"nombre": "Piercing", "duracion_min": 30, "precio": 18000, "grupo": "piercing", "paso_turno_min": 30},
    ],
}
