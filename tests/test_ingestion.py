"""Tests unitaires de l'ingestion (sans accès réseau ni GCP)."""

from __future__ import annotations

import gzip
from datetime import date

import pyarrow.parquet as pq
import pytest

from ingestion.download import build_url
from ingestion.months import add_months, file_name, month_range, parse_month
from ingestion.schema import EXPECTED_COLUMNS, KEPT_COLUMNS
from ingestion.transform import csv_to_parquet, inspect_header


def _write_sample(path, header, rows, sep=";"):
    with gzip.open(path, "wt", encoding="latin-1", newline="") as fh:
        fh.write(sep.join(header) + "\n")
        for r in rows:
            fh.write(sep.join(r) + "\n")


def _row(**values):
    return [values.get(c, "0") for c in EXPECTED_COLUMNS]


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "A202401.csv.gz"
    rows = [
        _row(FLX_ANN_MOI="202401", PRS_NAT="1111", PRS_PAI_MNT="26,50", PRS_REM_MNT="18,55",
             BEN_RES_REG="11", AGE_BEN_SNDS="30", BEN_SEX_COD="2"),
        _row(FLX_ANN_MOI="202401", PRS_NAT="3311", PRS_PAI_MNT=" 12.10 ", PRS_REM_MNT="12.10",
             BEN_RES_REG="", AGE_BEN_SNDS="80", BEN_SEX_COD="1"),
        _row(FLX_ANN_MOI="202401", PRS_NAT="4214", PRS_PAI_MNT="-5", PRS_REM_MNT="-5"),
    ]
    _write_sample(path, EXPECTED_COLUMNS, rows)
    return path


def test_parse_month():
    assert parse_month("2024-01") == date(2024, 1, 1)
    assert parse_month("202412") == date(2024, 12, 1)
    with pytest.raises(ValueError):
        parse_month("2024-13")


def test_month_range_and_add():
    assert month_range("2023-11", "2024-02") == [
        date(2023, 11, 1), date(2023, 12, 1), date(2024, 1, 1), date(2024, 2, 1)
    ]
    assert add_months(date(2024, 1, 1), -3) == date(2023, 10, 1)


def test_file_name_prefix():
    assert file_name(date(2024, 3, 1)) == "A202403.csv.gz"
    assert file_name(date(2014, 3, 1)) == "P201403.csv.gz"


def test_build_url():
    tpl = "https://x/download?file=Open_DAMIR/A{yyyymm}.csv.gz&y={year}&m={month}"
    assert build_url(tpl, date(2024, 2, 1)) == "https://x/download?file=Open_DAMIR/A202402.csv.gz&y=2024&m=02"


def test_inspect_header(sample):
    rep = inspect_header(sample)
    assert rep.separator == ";"
    assert rep.missing_expected == []
    assert rep.missing_kept == []


def test_inspect_header_alias_and_comma(tmp_path):
    header = [c if c != "BEN_RES_REG" else "ben_res_zeat" for c in EXPECTED_COLUMNS]
    path = tmp_path / "P201401.csv.gz"
    _write_sample(path, header, [_row()], sep=",")
    rep = inspect_header(path)
    assert rep.separator == ","
    assert "BEN_RES_REG" in rep.columns  # alias ZEAT -> REG et passage en majuscules


def test_missing_required_column(tmp_path):
    path = tmp_path / "A202401.csv.gz"
    _write_sample(path, ["FLX_ANN_MOI", "SOI_ANN"], [["202401", "2024"]])
    with pytest.raises(ValueError, match="obligatoires"):
        inspect_header(path)


def test_csv_to_parquet(sample, tmp_path):
    dest = tmp_path / "out" / "prestations.parquet"
    n = csv_to_parquet(sample, dest, date(2024, 1, 1), chunksize=2)
    assert n == 3
    table = pq.read_table(dest)
    assert table.column_names == KEPT_COLUMNS + ["_flx_month", "_source_file", "_ingested_at"]
    data = table.to_pydict()
    assert data["PRS_PAI_MNT"] == ["26,50", "12.10", "-5"]  # chaînes brutes, espaces retirés
    assert data["BEN_RES_REG"][1] is None  # chaîne vide -> NULL
    assert set(data["_flx_month"]) == {date(2024, 1, 1)}
    assert set(data["_source_file"]) == {"A202401.csv.gz"}


def test_csv_to_parquet_max_rows(sample, tmp_path):
    dest = tmp_path / "p.parquet"
    assert csv_to_parquet(sample, dest, date(2024, 1, 1), max_rows=2) == 2


def test_missing_kept_column_is_null(tmp_path):
    header = [c for c in EXPECTED_COLUMNS if c != "PSP_ACT_CAT"]
    path = tmp_path / "A202401.csv.gz"
    _write_sample(path, header, [[ "202401" if c == "FLX_ANN_MOI" else "1" for c in header]])
    dest = tmp_path / "p.parquet"
    csv_to_parquet(path, dest, date(2024, 1, 1))
    assert pq.read_table(dest).to_pydict()["PSP_ACT_CAT"] == [None]


# --- Mode sandbox (BigQuery sans compte de facturation) ---------------------

def test_sandbox_flag(monkeypatch):
    from ingestion.config import get_settings

    monkeypatch.delenv("BQ_SANDBOX", raising=False)
    assert get_settings().sandbox is True  # par défaut : sandbox
    for value, expected in [("false", False), ("0", False), ("True", True), ("oui", True)]:
        monkeypatch.setenv("BQ_SANDBOX", value)
        assert get_settings().sandbox is expected


def test_shard_table_name():
    from ingestion.gcp import shard_table

    assert shard_table("prestations", date(2024, 3, 1)) == "prestations_202403"


def test_sandbox_run_skips_gcs_and_loads_local_parquet(sample, tmp_path, monkeypatch):
    """En sandbox : pas d'upload GCS ni de bucket requis, chargement du Parquet local."""
    import ingestion.gcp as gcp
    from ingestion.cli import parquet_path, run
    from ingestion.config import get_settings

    monkeypatch.setenv("BQ_SANDBOX", "true")
    monkeypatch.setenv("GCP_PROJECT_ID", "projet-test")
    monkeypatch.setenv("GCS_BUCKET", "")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    def no_upload(*args, **kwargs):
        raise AssertionError("aucun envoi vers Cloud Storage en mode sandbox")

    calls = []

    def fake_load(project, dataset, table, location, local, month):
        calls.append((project, dataset, table, local, month))
        return 3

    monkeypatch.setattr(gcp, "upload_file", no_upload)
    monkeypatch.setattr(gcp, "load_month_from_file", fake_load)

    results = run([date(2024, 1, 1)], ["download", "transform", "upload", "load"],
                  local_file=sample)
    assert results[0]["rows_loaded"] == 3
    assert "gcs" not in results[0]
    project, dataset, table, local, month = calls[0]
    assert (project, dataset, table, month) == ("projet-test", "damir_raw", "prestations",
                                                date(2024, 1, 1))
    assert local == parquet_path(get_settings(), date(2024, 1, 1))
    assert local.exists()


def test_standard_mode_requires_bucket(monkeypatch):
    from ingestion.cli import step_load
    from ingestion.config import get_settings

    monkeypatch.setenv("BQ_SANDBOX", "false")
    monkeypatch.setenv("GCP_PROJECT_ID", "projet-test")
    monkeypatch.setenv("GCS_BUCKET", "")
    with pytest.raises(SystemExit, match="GCS_BUCKET"):
        step_load(date(2024, 1, 1), get_settings())
