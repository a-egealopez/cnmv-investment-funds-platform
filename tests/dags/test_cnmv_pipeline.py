"""DAG integrity: the file imports and wires the five stages as the README says.

Needs Airflow, so it is skipped in the project venv and run by CI inside the
Airflow image (see the airflow-build job).
"""

import importlib.util
import itertools
from pathlib import Path

import pytest

# "airflow.sdk", not "airflow": the repo's airflow/ folder imports as an empty package
pytest.importorskip("airflow.sdk")

DAG_FILE = Path(__file__).parents[2] / "dags" / "cnmv_pipeline.py"
STAGES = ["ingestion", "spark", "validate", "freshness", "dbt", "export"]


@pytest.fixture
def dag(monkeypatch):
    monkeypatch.setenv("HOST_PROJECT_DIR", "/project")
    spec = importlib.util.spec_from_file_location("cnmv_pipeline", DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.cnmv_pipeline()


def test_stages_run_in_order(dag):
    assert sorted(dag.task_ids) == sorted(STAGES)
    for upstream, downstream in itertools.pairwise(STAGES):
        assert dag.get_task(upstream).downstream_task_ids == {downstream}


def test_never_two_runs_at_once(dag):
    assert dag.max_active_runs == 1


def test_only_ingestion_retries(dag):
    retries = {task.task_id: task.retries for task in dag.tasks}
    assert retries.pop("ingestion") == 2
    assert set(retries.values()) == {0}


def test_every_stage_mounts_the_host_data_dir(dag):
    for task in dag.tasks:
        sources = [m["Source"] for m in task.mounts]
        assert sources == ["/project/data"], task.task_id
