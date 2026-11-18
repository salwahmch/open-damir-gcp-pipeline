"""Accès Google Cloud : dépôt dans Cloud Storage et chargement BigQuery."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from .months import yyyymm
from .schema import KEPT_COLUMNS

log = logging.getLogger(__name__)

LANDING_PREFIX = "open_damir/landing"  # fichiers bruts tels que publiés
PARQUET_PREFIX = "open_damir/parquet"  # fichiers convertis, partitionnés par mois


def landing_blob(month: date, file_name: str) -> str:
    return f"{LANDING_PREFIX}/year={month.year}/{file_name}"


def parquet_blob(month: date) -> str:
    return f"{PARQUET_PREFIX}/flx_month={month:%Y-%m}/prestations.parquet"


def upload_file(local: Path, bucket_name: str, blob_name: str, project: str) -> str:
    """Envoie un fichier dans GCS (upload résumable, idempotent)."""
    from google.cloud import storage

    client = storage.Client(project=project)
    blob = client.bucket(bucket_name).blob(blob_name)
    blob.chunk_size = 32 * 1024 * 1024  # upload résumable par blocs de 32 Mo
    if blob.exists(client):
        blob.reload(client=client)
        if blob.size == local.stat().st_size:
            log.info("Déjà présent dans GCS, envoi ignoré : gs://%s/%s", bucket_name, blob_name)
            return f"gs://{bucket_name}/{blob_name}"
    log.info("Envoi vers gs://%s/%s (%.1f Mo)", bucket_name, blob_name, local.stat().st_size / 1e6)
    blob.upload_from_filename(str(local), timeout=3600)
    return f"gs://{bucket_name}/{blob_name}"


def _raw_schema():
    from google.cloud import bigquery

    return [bigquery.SchemaField(c, "STRING") for c in KEPT_COLUMNS] + [
        bigquery.SchemaField("_flx_month", "DATE", mode="REQUIRED",
                             description="Mois de traitement (1er jour du mois)"),
        bigquery.SchemaField("_source_file", "STRING", description="Fichier source Open DAMIR"),
        bigquery.SchemaField("_ingested_at", "TIMESTAMP", description="Horodatage d'ingestion"),
    ]


def ensure_raw_table(project: str, dataset: str, table: str, location: str) -> None:
    """Crée la table brute partitionnée par mois et clusterisée si besoin."""
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery

    client = bigquery.Client(project=project, location=location)
    table_id = f"{project}.{dataset}.{table}"
    try:
        client.get_table(table_id)
        return
    except NotFound:
        pass
    t = bigquery.Table(table_id, schema=_raw_schema())
    t.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.MONTH, field="_flx_month"
    )
    t.clustering_fields = ["PRS_NAT", "BEN_RES_REG"]
    t.description = "Open DAMIR brut (colonnes en STRING, sous-ensemble des 55 variables)"
    client.create_table(t)
    log.info("Table créée : %s", table_id)


def load_month(project: str, dataset: str, table: str, location: str, gcs_uri: str,
               month: date) -> int:
    """Charge le Parquet du mois dans sa partition (WRITE_TRUNCATE = rejouable)."""
    from google.cloud import bigquery

    ensure_raw_table(project, dataset, table, location)
    client = bigquery.Client(project=project, location=location)
    destination = f"{project}.{dataset}.{table}${yyyymm(month)}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=_raw_schema(),
    )
    log.info("Chargement BigQuery %s -> %s", gcs_uri, destination)
    job = client.load_table_from_uri(gcs_uri, destination, job_config=job_config)
    job.result()
    rows = job.output_rows or 0
    log.info("Partition %s chargée : %d lignes", yyyymm(month), rows)
    return rows
