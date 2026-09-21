FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin ghost

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=ghost:ghost . .

RUN mkdir -p /app/data /app/investigations \
    && chown ghost:ghost /app/data /app/investigations

USER ghost

EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=ghost.backend.server
# Listen on all *container* interfaces so Docker port publishing can reach the
# app. Host-side publish stays on 127.0.0.1 in docker-compose.yml. The Python
# default without this override remains 127.0.0.1.
ENV GHOST_HOST=0.0.0.0

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health')"

CMD ["python", "-m", "ghost.backend.server"]
