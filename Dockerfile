FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=9202 \
    HOST=0.0.0.0 \
    CONFIG_PATH=/opt/libreqos/src/config.json \
    USERS_PATH=/opt/lqosync/users.json \
    LQOSYNC_RUN_MODE=host_nsenter \
    LQOSYNC_LIBREQOS_WORKING_DIR=/opt/libreqos/src \
    HOST_CONTROL_MODE=nsenter \
    LQOSYNC_USE_SUDO=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       util-linux procps iproute2 iputils-ping curl ca-certificates sudo \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN chmod +x /app/docker-entrypoint.sh || true

EXPOSE 9202
ENTRYPOINT ["/app/docker-entrypoint.sh"]
