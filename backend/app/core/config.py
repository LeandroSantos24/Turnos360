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

    # Orígenes permitidos por CORS. En dev, el front local; en producción, los
    # dominios reales separados por coma en la variable de entorno CORS_ORIGINS
    # (ej: "https://app.turnos360.com,https://turnos360.com").
    cors_origins: str = "http://localhost:3000"

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
    def _exigir_secret_en_produccion(self):
        # Fail-fast: si arrancás en producción sin un SECRET_KEY real, el backend
        # no levanta y te avisa, en vez de quedar inseguro en silencio.
        if self.es_produccion and self.secret_key.strip() in ("", PLACEHOLDER_SECRET):
            raise ValueError(
                "SECRET_KEY sin configurar en producción. Generá uno real con: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))" '
                "y seteá la variable de entorno SECRET_KEY."
            )
        return self


settings = Settings()