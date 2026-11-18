"""
### Pipeline Open DAMIR -> GCP

Chaque mois, l'Assurance Maladie publie le fichier des remboursements du mois
de traitement M (avec quelques mois de décalage). Ce DAG :

1. détermine le ou les mois à traiter (paramètre `months`, sinon mois logique - `lag_months`) ;
2. pour chaque mois, en parallèle (*dynamic task mapping*) : télécharge le CSV,
   le convertit en Parquet, dépose les fichiers dans Cloud Storage puis charge la
   partition BigQuery correspondante (rejouable sans doublon) ;
3. lance dbt : `deps` → `seed` → `run` → `test` → `docs generate`.

Déclenchement manuel avec des mois précis : *Trigger DAG w/ config*, par exemple
`{"months": ["2024-01", "2024-02"]}`. Pour un essai à faible coût :
`{"months": ["2024-01"], "max_rows": 200000}`.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import Param, dag, get_current_context, task

log = logging.getLogger(__name__)

DBT_DIR = os.getenv("DBT_PROJECT_DIR", "/opt/airflow/dbt")
DBT_BIN = os.getenv("DBT_BIN", "/opt/airflow/dbt_venv/bin/dbt")
DBT_TARGET = os.getenv("DBT_TARGET", "airflow")


def dbt_command(cmd: str) -> str:
    return f"cd {DBT_DIR} && {DBT_BIN} {cmd} --profiles-dir . --target {DBT_TARGET}"


@dag(
    dag_id="open_damir_pipeline",
    description="Open DAMIR : ingestion Python -> GCS -> BigQuery, puis transformations dbt",
    schedule="0 6 15 * *",  # le 15 de chaque mois à 6h UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    params={
        "months": Param([], type="array", description="Mois AAAA-MM à traiter (vide = automatique)"),
        "lag_months": Param(3, type="integer", minimum=0,
                            description="Décalage de publication utilisé en mode automatique"),
        "max_rows": Param(None, type=["null", "integer"],
                          description="Limiter le nombre de lignes lues (tests à faible coût)"),
        "keep_local_files": Param(False, type="boolean",
                                  description="Conserver les fichiers locaux après chargement"),
    },
    tags=["open-damir", "gcp", "dbt"],
    doc_md=__doc__,
)
def open_damir_pipeline():

    @task
    def resolve_months() -> list[str]:
        from ingestion.months import add_months, parse_month

        ctx = get_current_context()
        params = ctx["params"]
        if params["months"]:
            months = [f"{parse_month(m):%Y-%m}" for m in params["months"]]
        else:
            ref = ctx.get("logical_date") or datetime.now()
            target = add_months(date(ref.year, ref.month, 1), -int(params["lag_months"]))
            months = [f"{target:%Y-%m}"]
        log.info("Mois à traiter : %s", months)
        return months

    @task(retries=3, retry_delay=timedelta(minutes=10), execution_timeout=timedelta(hours=2))
    def download(month: str) -> str:
        from ingestion.cli import step_download
        from ingestion.config import get_settings
        from ingestion.months import parse_month

        step_download(parse_month(month), get_settings())
        return month

    @task(execution_timeout=timedelta(hours=2))
    def convert_to_parquet(month: str) -> str:
        from ingestion.cli import step_transform
        from ingestion.config import get_settings
        from ingestion.months import parse_month

        max_rows = get_current_context()["params"]["max_rows"]
        step_transform(parse_month(month), get_settings(), max_rows=max_rows)
        return month

    @task(execution_timeout=timedelta(hours=1))
    def upload_to_gcs(month: str) -> str:
        from ingestion.cli import step_upload
        from ingestion.config import get_settings
        from ingestion.months import parse_month

        uris = step_upload(parse_month(month), get_settings())
        log.info("Fichiers déposés : %s", uris)
        return month

    @task(execution_timeout=timedelta(hours=1))
    def load_to_bigquery(month: str) -> dict:
        from ingestion.cli import step_load
        from ingestion.config import get_settings
        from ingestion.months import parse_month

        rows = step_load(parse_month(month), get_settings())
        return {"month": month, "rows": rows}

    @task
    def cleanup_local_files(results: list[dict]) -> None:
        from ingestion.cli import landing_path, parquet_path
        from ingestion.config import get_settings
        from ingestion.months import parse_month

        if get_current_context()["params"]["keep_local_files"]:
            log.info("Fichiers locaux conservés")
            return
        settings = get_settings()
        for res in results:
            month = parse_month(res["month"])
            for path in (landing_path(settings, month), parquet_path(settings, month)):
                path.unlink(missing_ok=True)
                log.info("Supprimé : %s", path)

    months = resolve_months()
    loaded = load_to_bigquery.expand(
        month=upload_to_gcs.expand(month=convert_to_parquet.expand(month=download.expand(month=months)))
    )
    cleanup = cleanup_local_files(loaded)

    dbt_deps = BashOperator(task_id="dbt_deps", bash_command=dbt_command("deps"))
    dbt_seed = BashOperator(task_id="dbt_seed", bash_command=dbt_command("seed"))
    dbt_run = BashOperator(task_id="dbt_run", bash_command=dbt_command("run"))
    dbt_test = BashOperator(task_id="dbt_test", bash_command=dbt_command("test"), retries=0)
    dbt_docs = BashOperator(task_id="dbt_docs_generate", bash_command=dbt_command("docs generate"))

    loaded >> dbt_deps >> dbt_seed >> dbt_run >> dbt_test >> dbt_docs
    loaded >> cleanup


open_damir_pipeline()
