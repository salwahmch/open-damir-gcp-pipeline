"""Conversion CSV.gz -> Parquet, par blocs, sans charger le fichier en mémoire.

Un fichier mensuel Open DAMIR contient plusieurs millions de
lignes. On le lit par blocs (chunks) avec pandas, on ne garde que les colonnes
utiles, on ajoute trois colonnes techniques puis on écrit un Parquet
(un row group par bloc).
"""

from __future__ import annotations

import csv
import gzip
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .schema import COLUMN_ALIASES, EXPECTED_COLUMNS, KEPT_COLUMNS, REQUIRED_COLUMNS

log = logging.getLogger(__name__)

ENCODING = "latin-1"  # ne lève jamais d'erreur de décodage ; les valeurs sont des codes

ARROW_SCHEMA = pa.schema(
    [pa.field(c, pa.string()) for c in KEPT_COLUMNS]
    + [
        pa.field("_flx_month", pa.date32()),
        pa.field("_source_file", pa.string()),
        pa.field("_ingested_at", pa.timestamp("us", tz="UTC")),
    ]
)


@dataclass
class HeaderReport:
    separator: str
    columns: list[str]
    missing_expected: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    missing_kept: list[str] = field(default_factory=list)


def _normalise(name: str) -> str:
    name = name.strip().strip('"').lstrip("﻿").upper()
    return COLUMN_ALIASES.get(name, name)


def inspect_header(path: Path) -> HeaderReport:
    """Lit la 1re ligne, détecte le séparateur et compare au lexique."""
    with gzip.open(path, "rt", encoding=ENCODING, newline="") as fh:
        first = fh.readline()
    try:
        sep = csv.Sniffer().sniff(first, delimiters=";,|\t").delimiter
    except csv.Error:
        sep = ";"
    cols = [_normalise(c) for c in first.rstrip("\r\n").split(sep)]
    report = HeaderReport(
        separator=sep,
        columns=cols,
        missing_expected=[c for c in EXPECTED_COLUMNS if c not in cols],
        unexpected=[c for c in cols if c not in EXPECTED_COLUMNS],
        missing_kept=[c for c in KEPT_COLUMNS if c not in cols],
    )
    missing_required = REQUIRED_COLUMNS - set(cols)
    if missing_required:
        raise ValueError(
            f"{path.name} : colonnes obligatoires absentes {sorted(missing_required)}. "
            f"En-tête lu : {cols[:10]}..."
        )
    if report.missing_expected:
        log.warning("Colonnes du lexique absentes : %s", report.missing_expected)
    if report.unexpected:
        log.warning("Colonnes inattendues (ignorées) : %s", report.unexpected)
    if report.missing_kept:
        log.warning("Colonnes conservées absentes, remplies à NULL : %s", report.missing_kept)
    return report


def csv_to_parquet(
    src: Path,
    dest: Path,
    month: date,
    *,
    chunksize: int = 500_000,
    max_rows: int | None = None,
) -> int:
    """Convertit src (.csv.gz) en dest (.parquet). Renvoie le nombre de lignes."""
    report = inspect_header(src)
    present = [c for c in KEPT_COLUMNS if c in report.columns]
    ingested_at = datetime.now(UTC)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".parquet.part")

    reader = pd.read_csv(
        src,
        sep=report.separator,
        header=0,
        names=report.columns,  # noms normalisés (alias, majuscules)
        usecols=present,
        dtype=str,
        keep_default_na=False,  # on garde les chaînes telles quelles, le typage se fait dans dbt
        compression="gzip",
        encoding=ENCODING,
        chunksize=chunksize,
        nrows=max_rows,
    )

    total = 0
    with pq.ParquetWriter(tmp, ARROW_SCHEMA, compression="zstd") as writer:
        for i, chunk in enumerate(reader):
            for col in present:
                stripped = chunk[col].str.strip()
                chunk[col] = stripped.where(stripped != "", None)
            for col in KEPT_COLUMNS:
                if col not in chunk.columns:
                    chunk[col] = None
            chunk = chunk[KEPT_COLUMNS].copy()
            chunk["_flx_month"] = month
            chunk["_source_file"] = src.name
            chunk["_ingested_at"] = ingested_at
            table = pa.Table.from_pandas(chunk, schema=ARROW_SCHEMA, preserve_index=False)
            writer.write_table(table)
            total += len(chunk)
            log.info("Bloc %d écrit (%s lignes cumulées)", i + 1, f"{total:,}".replace(",", " "))

    _check_month(tmp, month)
    tmp.replace(dest)
    log.info("Parquet prêt : %s (%d lignes, %.1f Mo)", dest, total, dest.stat().st_size / 1e6)
    return total


def _check_month(path: Path, month: date) -> None:
    """Contrôle de cohérence : FLX_ANN_MOI doit correspondre au mois demandé."""
    expected = f"{month.year}{month.month:02d}"
    col = pq.read_table(path, columns=["FLX_ANN_MOI"]).column(0)
    values = {v for v in col.unique().to_pylist() if v}
    normalised = {v.replace("-", "")[:6] for v in values}
    if normalised and normalised != {expected}:
        log.warning(
            "FLX_ANN_MOI contient %s alors que le mois demandé est %s", sorted(values)[:5], expected
        )
