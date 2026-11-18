"""Téléchargement des fichiers mensuels Open DAMIR."""

from __future__ import annotations

import logging
import shutil
import time
from datetime import date
from pathlib import Path

import requests

from .months import file_name, yyyymm

log = logging.getLogger(__name__)

CHUNK = 8 * 1024 * 1024  # 8 Mo


def build_url(template: str, month: date) -> str:
    return template.format(yyyymm=yyyymm(month), year=month.year, month=f"{month.month:02d}")


def download_month(
    month: date,
    url_template: str,
    dest_dir: Path,
    *,
    retries: int = 3,
    timeout: int = 60,
) -> Path:
    """Télécharge le fichier du mois dans dest_dir (idempotent).

    Le fichier est écrit dans un .part puis renommé : un téléchargement
    interrompu ne laisse jamais un fichier tronqué considéré comme complet.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / file_name(month)
    url = build_url(url_template, month)

    if target.exists() and target.stat().st_size > 0:
        log.info("Déjà présent, téléchargement ignoré : %s", target)
        return target

    tmp = target.with_suffix(target.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            log.info("Téléchargement %s (tentative %d/%d)", url, attempt, retries)
            with requests.get(url, stream=True, timeout=timeout) as resp:
                resp.raise_for_status()
                ctype = resp.headers.get("Content-Type", "")
                if "text/html" in ctype:
                    raise RuntimeError(
                        f"Le serveur a renvoyé une page HTML et non un fichier : vérifiez "
                        f"DAMIR_URL_TEMPLATE ({url})"
                    )
                with open(tmp, "wb") as fh:
                    shutil.copyfileobj(resp.raw, fh, CHUNK)
            _check_gzip(tmp)
            tmp.replace(target)
            log.info("OK : %s (%.1f Mo)", target, target.stat().st_size / 1e6)
            return target
        except (requests.RequestException, RuntimeError, OSError) as exc:
            log.warning("Échec : %s", exc)
            tmp.unlink(missing_ok=True)
            if attempt == retries:
                raise
            time.sleep(10 * attempt)
    raise AssertionError("unreachable")


def _check_gzip(path: Path) -> None:
    with open(path, "rb") as fh:
        if fh.read(2) != b"\x1f\x8b":
            raise RuntimeError(f"{path.name} n'est pas un fichier gzip valide")
