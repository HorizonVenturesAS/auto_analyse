from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from .analysis import analyze_file
from .config import load_config
from .report import build_report


SUPPORTED_PATTERNS = ("*.csv", "*.csv.gz", "*.zip", "*.xlsx", "*.xls")


def _discover_latest(search_dirs: Iterable[Path]) -> Path:
    candidates: list[Path] = []
    for directory in search_dirs:
        if not directory.exists():
            continue
        for pattern in SUPPORTED_PATTERNS:
            candidates.extend(path for path in directory.glob(pattern) if path.is_file())
    if not candidates:
        raise FileNotFoundError(
            "Fant ingen råfil. Legg en CSV/ZIP/XLSX i data/inbox eller oppgi filbanen eksplisitt."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Kan ikke serialisere {type(value)!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lag standard pris- og tilgjengelighetsrapport fra crawl-data."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="CSV, CSV.GZ, ZIP eller XLSX. Nyeste fil oppdages automatisk hvis utelatt.",
    )
    parser.add_argument("-o", "--output", help="Målfil for .xlsx-rapporten")
    parser.add_argument("--config", default="config/report.toml", help="TOML-konfigurasjon")
    parser.add_argument(
        "--source-url", default=None, help="Valgfri sporbar kilde-URL som vises i rapporten"
    )
    args = parser.parse_args(argv)

    source = (
        Path(args.input)
        if args.input
        else _discover_latest([Path("data/inbox"), Path("examples/raw")])
    )
    if not source.exists():
        parser.error(f"Filen finnes ikke: {source}")
    output = (
        Path(args.output)
        if args.output
        else Path("outputs") / f"{source.stem}_innsiktsrapport.xlsx"
    )
    config = load_config(args.config)
    result = analyze_file(source, config, source_url=args.source_url)
    report_path = build_report(result, config, output)
    manifest_path = report_path.with_suffix(".json")
    manifest_path.write_text(
        json.dumps(result.summary, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "input": str(source),
                "report": str(report_path),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )
    return 0
