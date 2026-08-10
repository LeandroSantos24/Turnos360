"""Engine y sesiones. get_db es la dependencia base de FastAPI (se usa desde E2)."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# pool_pre_ping: antes de usar una conexión del pool, la prueba con un ping.
#   Sin esto, una conexión que el servidor cerró de su lado (reinicio de
#   Postgres, corte de red del VPS) explota en la CARA del usuario con
#   "server closed the connection unexpectedly" en un request cualquiera.
#
# pool_recycle: recicla las conexiones antes de los 30 minutos. Los proveedores
#   de VPS y los balanceadores suelen cortar conexiones TCP ociosas sin avisar;
#   reciclarlas antes evita depender del pre_ping para el caso normal.
#
# pool_size / max_overflow: 5 permanentes + 10 de pico POR PROCESO de uvicorn.
#   Con 2 workers son hasta 30 conexiones, y Postgres viene con un techo de 100
#   por defecto. Es holgado para 10-15 negocios y deja margen para el worker de
#   Celery y para entrar con psql sin quedarte sin cupo.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()