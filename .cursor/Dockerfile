# Cloud Agent base image for BeTaxed.
# Installs pinned toolchains only. Cursor checks out the repo separately — do not COPY the app.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        gnupg \
        lsb-release \
        openssh-client \
        sudo \
        build-essential \
        software-properties-common \
        gpg-agent \
    && rm -rf /var/lib/apt/lists/*

# Python 3.13 — Ubuntu 24.04 ships 3.12; BeTaxed pins 3.13.
RUN add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.13 \
        python3.13-venv \
        python3.13-dev \
    && rm -rf /var/lib/apt/lists/*

# Node.js 24 — frontend engines.node is >=24.
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# PostgreSQL 18
RUN install -d /etc/apt/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-18 \
        postgresql-client-18 \
        postgresql-contrib-18 \
    && rm -rf /var/lib/apt/lists/*

# Redis 8 (binary only; start script launches it on 6380)
RUN curl -fsSL https://packages.redis.io/gpg \
        | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg \
    && chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(. /etc/os-release && echo "$VERSION_CODENAME") main" \
        > /etc/apt/sources.list.d/redis.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends redis \
    && rm -rf /var/lib/apt/lists/*

# Package postinst usually creates 18/main; ensure it exists and is not left running in the image.
RUN if [ ! -d /etc/postgresql/18/main ]; then pg_createcluster 18 main; fi \
    && pg_ctlcluster 18 main stop || true

RUN id -u ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu \
    && usermod -aG sudo ubuntu \
    && echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu \
    && chmod 440 /etc/sudoers.d/ubuntu

USER ubuntu
WORKDIR /home/ubuntu
