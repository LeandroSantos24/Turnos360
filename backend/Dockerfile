# Imagen de DESARROLLO del backend.
#
# El compose de dev monta ../backend:/app encima de esto, así que el contenido
# copiado acá casi no se usa: lo que corre es el código del host, con --reload.
# Corre como root a propósito: el volumen montado pertenece al usuario del host
# y un usuario sin privilegios no podría escribir __pycache__ ni el schedule
# del beat de Celery.
#
# Para producción está backend/Dockerfile.prod (multi-stage, sin privilegios),
# que es el que usa infra/docker-compose.prod.yml.

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
