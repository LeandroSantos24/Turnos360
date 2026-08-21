"""Configuración central (pydantic-settings). Lee variables de entorno / .env."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor de relleno: sirve en desarrollo, pero está PROHIBIDO en producción.
PLACEHOLDER_SECRET = "cambiar-en-produccion"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"

    # --- Observabilidad ------------------------------------------------
    # Antes no había NADA: ni logging configurado, ni manejador global de
    # excepciones, ni alertas. Un error en producción se descubría porque
    # llamaba un cliente.
    #
    # log_json: en producción conviene (una línea de JSON por evento, para
    # filtrar con jq o mandar a un agregador). En dev, humano y con color.
    log_level: str = "INFO"
    log_json: bool = False
    # Sentry es OPCIONAL: sin DSN el sistema anda igual. Ponerlo es lo que
    # convierte "me enteré por un cliente" en "me llegó una alerta".
    sentry_dsn: str = ""
    database_url: str = "postgresql+psycopg://turnos360:turnos360@localhost:5432/turnos360"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = PLACEHOLDER_SECRET

    # Clave propia para la encriptación Fernet de las credenciales por empresa
    # (Mercado Pago / WhatsApp / email). SEPARADA de SECRET_KEY a propósito:
    # los JWT y las credenciales guardadas tienen ciclos de vida distintos, y
    # rotar la firma de los tokens (p. ej. ante una sospecha de leak) no debe
    # romper lo que ya está encriptado en la base.
    # En dev puede quedar vacía (crypto deriva de SECRET_KEY, como siempre);
    # en producción es OBLIGATORIA y distinta de SECRET_KEY.
    fernet_key: str = ""

    # Orígenes permitidos por CORS. En dev, el front local; en producción, los
    # dominios reales separados por coma en la variable de entorno CORS_ORIGINS
    # (ej: "https://app.turnos360.com,https://turnos360.com").
    cors_origins: str = "http://localhost:3000"

    # URLs base (deploy: dominio real). public = vidriera/landing; api = backend.
    public_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    # Email saliente (Gmail SMTP con contraseña de aplicación; gratis ~500/día).
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""          # turnos360.contacto@gmail.com
    smtp_pass: str = ""          # contraseña de APLICACIÓN (no la de la cuenta)
    smtp_from: str = ""          # opcional; default = smtp_user

    # ── WhatsApp ──────────────────────────────────────────────────────
    # El freno de mano del sistema. Con 'simulado' NO sale un mensaje a la
    # calle aunque todas las empresas tengan sus tokens cargados: el
    # circuito corre entero (descuenta saldo, registra el mensaje, escribe
    # el texto en el log) pero nadie recibe nada. Es el default a
    # propósito: para pasar a 'meta' hay que decidirlo.
    wa_proveedor: str = "simulado"          # simulado | meta
    wa_api_version: str = "v21.0"
    wa_idioma_plantillas: str = "es_AR"
    # Precio de venta de UN mensaje, en pesos. Calculado sobre el PEOR
    # escenario de tarifa (USD 0,0260) + impuestos + 20 % de rentabilidad.
    # Ver app/services/creditos_wa.py. Se cambia acá cuando se mueva el
    # dólar o cuando sepamos la tarifa real de Meta para Argentina.
    wa_precio_mensaje_ars: float = 73.0
    # Webhook de estados. Sin estos dos, el endpoint público rechaza todo:
    # es un endpoint sin autenticación nuestra y la firma es la única
    # defensa contra que cualquiera marque mensajes como leídos.
    # Meta cobra los mensajes de servicio (las respuestas dentro de la
    # ventana de 24 h) A PARTIR DEL 1 DE OCTUBRE DE 2026. Hasta esa fecha
    # son gratis y no tiene sentido descontarle crédito al negocio por
    # algo que no nos cuesta. Ese día: WA_COBRAR_SERVICIO=true en el .env.
    wa_cobrar_servicio: bool = False
    # ── Firma del webhook de Mercado Pago ────────────────────────────
    # Tres estados a propósito, porque esto es plata y no se puede probar
    # en local: 'off' se comporta como antes; 'log' valida y AVISA sin
    # bloquear (para confirmar contra tráfico real que la firma cierra);
    # 'enforce' rechaza lo que no venga firmado. Se sube un escalón por
    # vez, mirando los logs. Ver routers/publico.py.
    mp_firma_modo: str = "off"          # off | log | enforce
    mp_webhook_secret: str = ""
    wa_webhook_verify_token: str = ""
    wa_app_secret: str = ""

    # Zona horaria de los negocios. El motor de agenda trabaja con "hora de
    # pared etiquetada UTC" (un turno de las 10:00 se guarda como 10:00+00:00),
    # así que para saber si un horario ya pasó hay que preguntar qué hora es
    # ACÁ, no en UTC. Sin esto, en un servidor con TZ=UTC el sistema se cree
    # 3 horas en el futuro respecto del local.
    zona_horaria: str = "America/Argentina/Buenos_Aires"

    # --- Datos de cobranza de Turnos360 (los TUYOS, no los del negocio) ------
    # Se le muestran al dueño en "Mi suscripción" para que te transfiera.
    # Van por entorno y NO hardcodeados: el repo es público y el CUIT/CUIL es
    # dato personal — una vez que entra en un commit queda en el historial de
    # git para siempre, aunque después se borre del archivo.
    cobro_cbu: str = ""
    cobro_alias: str = ""
    cobro_titular: str = ""
    cobro_cuit: str = ""
    cobro_banco: str = ""
    # Link de pago de Mercado Pago (el permanente de tu cuenta). Vacío = solo
    # se ofrece transferencia.
    cobro_mp_link: str = ""
    # WhatsApp al que el negocio manda el comprobante de la transferencia.
    # Formato wa.me: 5492613456599
    cobro_whatsapp: str = ""

    # --- Precio de lista del SaaS -------------------------------------------
    # Cuota mensual con la que nace toda empresa nueva y que muestra la landing.
    # Vive acá y no repartido por el código: cambiar el precio tiene que ser
    # tocar UN número, no salir a buscarlo por cinco archivos.
    # Si cambia, actualizar también frontend/src/lib/precios.ts (el número de
    # la landing se compila en el bundle y no puede leer esta variable).
    precio_lista_mensual: float = 14990

    # --- Precio promocional (opcional) --------------------------------------
    # Estrategia de lanzamiento: si PROMO_ACTIVA=true, la landing muestra el
    # precio normal tachado y el promocional al lado, y las empresas nuevas
    # nacen con el promocional cargado. Si está en false, no existe: se ve
    # solo el precio normal y no hay rastro de promoción en ningún lado.
    # Se prende y se apaga sin tocar código.
    promo_activa: bool = False
    precio_promo_mensual: float = 11990
    promo_etiqueta: str = "Precio de lanzamiento"

    # --- Alerta de acceso al panel de super-admin ---------------------------
    # A dónde avisar cuando alguien entra (o intenta entrar) a /admin/login.
    # Ese usuario controla TODOS los negocios del sistema: si alguien entra
    # y no fuiste vos, querés enterarte en el momento, no en la auditoría.
    # Vacío = no se manda nada (útil en desarrollo, para no llenarte la casilla).
    admin_alerta_email: str = "turnos360.oficial@gmail.com"
    # Avisar también los intentos FALLIDOS. Es el dato que de verdad sirve:
    # un login exitoso tuyo es rutina; tres fallidos seguidos a las 4 AM no.
    admin_alerta_fallidos: bool = True
    # En desarrollo el aviso molesta más de lo que ayuda (entrás veinte veces
    # por día). Poné ADMIN_ALERTA_EN_DEV=true si querés probarlo localmente.
    admin_alerta_en_dev: bool = False
    # Averiguar de dónde salió la conexión (ciudad, país, proveedor) para
    # incluirlo en el aviso. Es el dato que más rápido te dice si fuiste vos:
    # "Mendoza, Argentina" es tu casa, "Frankfurt" no.
    # Consulta un servicio gratuito mandándole SOLO la IP. Si no responde, el
    # mail sale igual sin ese dato. Nada de esto se guarda en la base.
    # Poné false si preferís no consultar servicios externos.
    admin_alerta_geolocalizar: bool = True

    # --- JWT (E2) ---
    jwt_algoritmo: str = "HS256"
    access_token_minutos: int = 30      # token corto: viaja en cada request
    refresh_token_dias: int = 7         # token largo: solo para renovar el corto

    @property
    def es_produccion(self) -> bool:
        return self.env.lower() in {"prod", "produccion", "production"}

    @property
    def precio_vigente(self) -> float:
        """El precio que se cobra hoy: el promocional si la promo está activa."""
        if self.promo_activa and self.precio_promo_mensual > 0:
            return self.precio_promo_mensual
        return self.precio_lista_mensual

    @property
    def avisar_acceso_admin(self) -> bool:
        """¿Corresponde mandar el aviso de acceso al panel de super-admin?"""
        if not self.admin_alerta_email.strip():
            return False
        return self.es_produccion or self.admin_alerta_en_dev

    @property
    def cors_origins_lista(self) -> list[str]:
        """Convierte el string de orígenes en la lista que espera el middleware."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _exigir_secretos_en_produccion(self):
        # Fail-fast: si arrancás en producción sin secretos reales, el backend
        # no levanta y te avisa, en vez de quedar inseguro en silencio.
        if not self.es_produccion:
            return self

        generar = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'

        if self.secret_key.strip() in ("", PLACEHOLDER_SECRET):
            raise ValueError(
                "SECRET_KEY sin configurar en producción. Generá uno real con: "
                f"{generar} y seteá la variable de entorno SECRET_KEY."
            )
        if not self.fernet_key.strip():
            raise ValueError(
                "FERNET_KEY sin configurar en producción. Encripta las credenciales "
                "de MP/WhatsApp/email y debe ser propia (no derivada de SECRET_KEY). "
                f"Generá una con: {generar} y seteá la variable de entorno FERNET_KEY."
            )
        if self.fernet_key.strip() == self.secret_key.strip():
            raise ValueError(
                "FERNET_KEY no puede ser igual a SECRET_KEY: la separación existe "
                "para poder rotar la firma de los JWT sin romper las credenciales "
                "guardadas. Generá una FERNET_KEY propia."
            )
        return self


settings = Settings()
