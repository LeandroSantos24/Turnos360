"""Configuración central (pydantic-settings). Lee variables de entorno / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://turnos360:turnos360@localhost:5432/turnos360"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "cambiar-en-produccion"


settings = Settings()
