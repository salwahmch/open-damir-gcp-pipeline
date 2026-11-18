"""Vérifie que le DAG Airflow s'importe sans erreur et a la structure attendue."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("airflow")

DAGS_DIR = Path(__file__).resolve().parents[1] / "airflow" / "dags"


def test_dag_imports_and_structure():
    from airflow.dag_processing.dagbag import DagBag

    bag = DagBag(dag_folder=str(DAGS_DIR))
    assert bag.import_errors == {}
    dag = bag.dags.get("open_damir_pipeline")
    assert dag is not None
    expected = {
        "resolve_months", "download", "convert_to_parquet", "upload_to_gcs",
        "load_to_bigquery", "cleanup_local_files", "dbt_deps", "dbt_seed",
        "dbt_run", "dbt_test", "dbt_docs_generate",
    }
    assert expected <= set(dag.task_ids)
    assert dag.get_task("dbt_run").downstream_task_ids == {"dbt_test"}
    assert "dbt_deps" in dag.get_task("load_to_bigquery").downstream_task_ids
