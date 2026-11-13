FROM python:3.12-slim

WORKDIR /app/dbt

COPY requirements-dbt.txt ./
RUN pip install --no-cache-dir -r requirements-dbt.txt

RUN useradd --create-home --uid 1000 app \
    && mkdir /data \
    && chown -R app:app /data /app
COPY --chown=app:app dbt/ /app/dbt/
USER app

ENV CNMV_DATA_DIR=/data
ENV DBT_PROFILES_DIR=/app/dbt

RUN dbt deps

ENTRYPOINT ["dbt"]
CMD ["build"]