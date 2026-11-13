FROM python:3.12-slim

WORKDIR /app/dbt

COPY requirements/dbt.txt ./
RUN pip install --no-cache-dir -r dbt.txt

RUN useradd --create-home --uid 1000 app \
    && mkdir /data \
    && chown -R app:app /data /app
COPY --chown=app:app dbt/ /app/dbt/
USER app

ENV CNMV_DATA_DIR=/data
ENV DBT_PROFILES_DIR=/app/dbt
ENV PYTHONPATH=/app

RUN dbt deps

COPY --chown=app:app config.py /app/config.py
COPY --chown=app:app bi/ /app/bi/

ENTRYPOINT ["sh", "-c", "mkdir -p /data/gold && exec dbt \"$@\"", "--"]
CMD ["build"]