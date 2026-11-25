"""Point d'entrée en ligne de commande.

Exemples :
    python -m ingestion run --month 2024-01
    python -m ingestion run --from 2024-01 --to 2024-03
    python -m ingestion run --month 2024-01 --steps download,transform
    python -m ingestion run --month 2024-01 --local-file ~/Téléchargements/A202401.csv.gz
    python -m ingestion run --month 2024-01 --max-rows 200000   # mode test, peu coûteux
    python -m ingestion inspect data/landing/A202401.csv.gz

En mode sandbox (BQ_SANDBOX=true, par défaut) l'étape upload est ignorée et
l'étape load envoie directement le Parquet local dans BigQuery.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from datetime import date
from pathlib import Path

from .config import Settings, get_settings, require
from .months import file_name, month_range, parse_month

STEPS = ("download", "transform", "upload", "load")
log = logging.getLogger("ingestion")


def landing_path(settings: Settings, month: date) -> Path:
    return settings.data_dir / "landing" / file_name(month)


def parquet_path(settings: Settings, month: date) -> Path:
    return settings.data_dir / "parquet" / f"flx_month={month:%Y-%m}" / "prestations.parquet"


# Chaque étape est une fonction autonome : le DAG Airflow les appelle une à une.

def step_download(month: date, settings: Settings, local_file: Path | None = None) -> Path:
    from .download import download_month

    target = landing_path(settings, month)
    if local_file:
        target.parent.mkdir(parents=True, exist_ok=True)
        if local_file.resolve() != target.resolve():
            shutil.copy2(local_file, target)
        log.info("Fichier local utilisé : %s", local_file)
        return target
    return download_month(month, settings.url_template, target.parent)


def step_transform(month: date, settings: Settings, max_rows: int | None = None) -> Path:
    from .transform import csv_to_parquet

    src, dest = landing_path(settings, month), parquet_path(settings, month)
    if not src.exists():
        raise FileNotFoundError(f"{src} introuvable : lancez d'abord l'étape download")
    csv_to_parquet(src, dest, month, max_rows=max_rows)
    return dest


def step_upload(month: date, settings: Settings, skip_landing: bool = False) -> dict[str, str]:
    from .gcp import landing_blob, parquet_blob, upload_file

    if settings.sandbox:
        log.info("Mode sandbox : pas de Cloud Storage, étape upload ignorée")
        return {}
    require(settings, "project_id", "bucket")
    uris = {}
    if not skip_landing:
        src = landing_path(settings, month)
        uris["landing"] = upload_file(src, settings.bucket, landing_blob(month, src.name),
                                      settings.project_id)
    uris["parquet"] = upload_file(parquet_path(settings, month), settings.bucket,
                                  parquet_blob(month), settings.project_id)
    return uris


def step_load(month: date, settings: Settings) -> int:
    from .gcp import load_month, load_month_from_file, parquet_blob

    if settings.sandbox:
        require(settings, "project_id")
        return load_month_from_file(settings.project_id, settings.raw_dataset,
                                    settings.raw_table, settings.location,
                                    parquet_path(settings, month), month)
    require(settings, "project_id", "bucket")
    uri = f"gs://{settings.bucket}/{parquet_blob(month)}"
    return load_month(settings.project_id, settings.raw_dataset, settings.raw_table,
                      settings.location, uri, month)


def run(months: list[date], steps: list[str], *, local_file: Path | None = None,
        max_rows: int | None = None, skip_landing: bool = False) -> list[dict]:
    settings = get_settings()
    results = []
    for month in months:
        res: dict = {"month": f"{month:%Y-%m}"}
        log.info("===== Mois %s : étapes %s =====", res["month"], ",".join(steps))
        if "download" in steps:
            res["landing_file"] = str(step_download(month, settings, local_file))
        if "transform" in steps:
            res["parquet_file"] = str(step_transform(month, settings, max_rows))
        if "upload" in steps and not settings.sandbox:
            res["gcs"] = step_upload(month, settings, skip_landing)
        if "load" in steps:
            res["rows_loaded"] = step_load(month, settings)
        results.append(res)
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ingestion", description="Ingestion Open DAMIR -> BigQuery")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Exécuter le pipeline d'ingestion")
    grp = p_run.add_mutually_exclusive_group(required=True)
    grp.add_argument("--month", action="append", help="Mois AAAA-MM (répétable)")
    grp.add_argument("--from", dest="start", help="Premier mois AAAA-MM (avec --to)")
    p_run.add_argument("--to", dest="end", help="Dernier mois AAAA-MM")
    p_run.add_argument("--steps", default=",".join(STEPS),
                       help=f"Étapes séparées par des virgules parmi {STEPS}")
    p_run.add_argument("--local-file", type=Path,
                       help="Utiliser un fichier déjà téléchargé (un seul mois)")
    p_run.add_argument("--max-rows", type=int, help="Ne lire que N lignes (tests à faible coût)")
    p_run.add_argument("--skip-landing-upload", action="store_true",
                       help="Ne pas déposer le CSV brut dans GCS (seulement le Parquet)")

    p_insp = sub.add_parser("inspect", help="Afficher l'en-tête d'un fichier et l'écart au lexique")
    p_insp.add_argument("path", type=Path)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    if args.cmd == "inspect":
        from .transform import inspect_header

        rep = inspect_header(args.path)
        print(json.dumps(rep.__dict__, indent=2, ensure_ascii=False))
        return

    if args.start:
        if not args.end:
            parser.error("--from nécessite --to")
        months = month_range(args.start, args.end)
    else:
        months = [parse_month(m) for m in args.month]

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = set(steps) - set(STEPS)
    if unknown:
        parser.error(f"Étapes inconnues : {sorted(unknown)}")
    if args.local_file and len(months) != 1:
        parser.error("--local-file ne s'utilise qu'avec un seul mois")

    results = run(months, steps, local_file=args.local_file, max_rows=args.max_rows,
                  skip_landing=args.skip_landing_upload)
    print(json.dumps(results, indent=2, ensure_ascii=False))
