FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# WeasyPrint 53+ больше не требует gdk-pixbuf и cairo — только Pango.
# Debian 12 (bookworm, на которой python:3.12-slim) переименовал libgdk-pixbuf2.0-0 → libgdk-pixbuf-2.0-0.
# Чтобы избежать ломких имён пакетов, оставляем минимум для WeasyPrint 63+.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libffi-dev \
        shared-mime-info \
        fonts-liberation \
        fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/data/checkups && chmod 777 /var/data/checkups

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY . .

EXPOSE 8000

CMD ["python", "-m", "src.main"]
