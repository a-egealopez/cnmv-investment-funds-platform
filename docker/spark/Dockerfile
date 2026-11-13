FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/spark.txt ./
RUN pip install --no-cache-dir -r spark.txt

COPY config.py ./
COPY spark/ spark/

RUN useradd --create-home --uid 1000 app \
    && mkdir /data \
    && chown app:app /data
USER app

ENV CNMV_DATA_DIR=/data

ENTRYPOINT ["python", "-m", "spark.jobs.build_silver"]