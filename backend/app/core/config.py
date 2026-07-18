"""Configuración central (pydantic-settings). Lee variables de entorno / .env."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor de relleno: sirve en desarrollo, pero está PROHIBIDO en producción.
PLACEHOLDER_SECRET = "cambiar-en-produccion"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
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

    # --- JWT (E2) ---
    jwt_algoritmo: str = "HS256"
    access_token_minutos: int = 30      # token corto: viaja en cada request
    refresh_token_dias: int = 7         # token largo: solo para renovar el corto

    @property
    def es_produccion(self) -> bool:
        return self.env.lower() in {"prod", "produccion", "production"}

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
