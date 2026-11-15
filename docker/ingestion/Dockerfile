FROM python:3.12-slim

# Debian security patches released after the base image was built
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ingestion.txt ./
RUN pip install --no-cache-dir -r ingestion.txt

COPY config.py ./
COPY ingestion/ ingestion/

RUN useradd --create-home --uid 1000 app \
    && mkdir /data \
    && chown app:app /data
USER app

ENV CNMV_DATA_DIR=/data

ENTRYPOINT ["python", "-m", "ingestion.run"]