"""Manipulation des mois de traitement (format AAAA-MM)."""

from __future__ import annotations

import re
from datetime import date

_MONTH_RE = re.compile(r"^(\d{4})-?(\d{2})$")


def parse_month(value: str) -> date:
    """'2024-01' ou '202401' -> date(2024, 1, 1)."""
    m = _MONTH_RE.match(value.strip())
    if not m:
        raise ValueError(f"Mois invalide : {value!r} (attendu AAAA-MM)")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise ValueError(f"Mois invalide : {value!r}")
    return date(year, month, 1)


def add_months(d: date, n: int) -> date:
    idx = d.year * 12 + (d.month - 1) + n
    return date(idx // 12, idx % 12 + 1, 1)


def month_range(start: str, end: str) -> list[date]:
    """Liste inclusive des mois entre start et end."""
    first, last = parse_month(start), parse_month(end)
    if first > last:
        raise ValueError("Le mois de début est postérieur au mois de fin")
    out, cur = [], first
    while cur <= last:
        out.append(cur)
        cur = add_months(cur, 1)
    return out


def yyyymm(d: date) -> str:
    return f"{d.year}{d.month:02d}"


def file_name(d: date) -> str:
    """Nom officiel du fichier mensuel (préfixe A depuis 2015, P avant)."""
    prefix = "A" if d.year >= 2015 else "P"
    return f"{prefix}{yyyymm(d)}.csv.gz"
