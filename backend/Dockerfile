# Smart Transit AI — backend image (Django 6 + DRF + Channels + Celery).
# Python 3.13: latest stable supported by every dependency (Celery 5.6 caps at 3.13).
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# psycopg[binary] ships manylinux wheels, so no build toolchain or libpq-dev needed.
COPY requirements/ requirements/
RUN pip install --upgrade pip && pip install -r requirements/prod.txt

COPY . .

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

# 8000 = HTTP/DRF (gunicorn or runserver), 9000 = WebSocket/ASGI (daphne).
EXPOSE 8000 9000

# Default command; each compose service overrides this.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
