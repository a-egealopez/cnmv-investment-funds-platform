"""CNMV pipeline: ingestion -> spark -> validate -> freshness -> dbt -> export.

Airflow only orchestrates. Each stage is one of the project's images, started as a
sibling container; the stage's exit code decides success or failure. The pipeline is
incremental: ingestion downloads whatever the CNMV has published since HISTORY_START
and Spark builds only the periods that are new or changed, so a run needs no date.
"""

import os
from datetime import timedelta

import pendulum
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import dag
from docker.types import Mount

HISTORY_START = "202001"
DATA_MOUNT = Mount(
    source=f"{os.environ['HOST_PROJECT_DIR']}/data",
    target="/data",
    type="bind",
)


def stage(task_id, image, command=None, entrypoint=None, **kwargs):
    return DockerOperator(
        task_id=task_id,
        image=image,
        command=command,
        entrypoint=entrypoint,
        mounts=[DATA_MOUNT],
        environment={
            "SPARK_DRIVER_MEMORY": os.environ.get("SPARK_DRIVER_MEMORY", "3g")
        },
        auto_remove="success",
        mount_tmp_dir=False,
        docker_url="unix://var/run/docker.sock",
        **kwargs,
    )


@dag(
    schedule="@weekly",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    # One run at a time: the stages share data/ and DuckDB has a single writer.
    max_active_runs=1,
    default_args={"execution_timeout": timedelta(hours=1)},
    tags=["cnmv"],
    doc_md=__doc__,
)
def cnmv_pipeline():
    # Retries are for transient failures (network); a month not yet published is not one.
    ingestion = stage(
        "ingestion",
        "cnmv-ingestion",
        f"--since {HISTORY_START}",
        retries=2,
        retry_delay=timedelta(minutes=10),
    )
    spark = stage("spark", "cnmv-spark", "--pending")
    validate = stage(
        "validate",
        "cnmv-spark",
        entrypoint=["python", "-m", "spark.jobs.validate_silver"],
    )
    # Warns when a source is older than its publication cadence; never fails the run
    freshness = stage("freshness", "cnmv-dbt", "source freshness")
    dbt = stage("dbt", "cnmv-dbt", "build")
    export = stage(
        "export",
        "cnmv-dbt",
        entrypoint=["python", "-m", "bi.export_gold"],
    )

    ingestion >> spark >> validate >> freshness >> dbt >> export


cnmv_pipeline()
