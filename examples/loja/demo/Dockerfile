# Spark local com o orquestrador do datapacto. Construído a partir da raiz do repositório
# (o docker-compose.yml já aponta o contexto para lá).
FROM python:3.11-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
 && rm -rf /var/lib/apt/lists/*

COPY packages/orchestrator /src/orchestrator
RUN pip install --no-cache-dir "pyspark==3.5.3" /src/orchestrator

WORKDIR /work
