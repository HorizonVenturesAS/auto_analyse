from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Iterable

import numpy as np

from .analysis import analyze_file
from .config import load_config
from .io_utils import validate_outputs
from .report import build_report, header_note_specs

SUPPORTED_PATTERNS = ("*.csv", "*.csv.gz", "*.zip", "*.xlsx")
DEMO = Path("examples/demo/retail.csv")


def _discover_latest(search_dirs: Iterable[Path]) -> Path:
    """Directories are ordered fallbacks; never prefer a demo over inbox data."""
    for directory in search_dirs:
        candidates = [path for pattern in SUPPORTED_PATTERNS for path in directory.glob(pattern) if path.is_file() and not path.name.startswith("~$")]
        if candidates:
            return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))
    raise FileNotFoundError("Fant ingen råfil. Legg en CSV/CSV.GZ/ZIP/XLSX i data/inbox eller oppgi filbanen.")


def _json_value(value):
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    return None if isinstance(value, float) and not math.isfinite(value) else value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lag pris- og tilgjengelighetsrapport fra en lokal råfil.")
    parser.add_argument("input", nargs="?", help="CSV, CSV.GZ, ZIP med én CSV eller XLSX.")
    parser.add_argument("-o", "--output", help="Målfil for .xlsx-rapporten")
    parser.add_argument("--config", help="TOML-konfigurasjon. Standard: config/report.toml hvis den finnes.")
    parser.add_argument("--source-url", help="Valgfri sporbar kilde-URL i rapporten")
    parser.add_argument("--demo", action="store_true", help="Bruk utelukkende den syntetiske retaildemoen.")
    parser.add_argument("--overwrite", action="store_true", help="Tillat overskriving av eksisterende rapport og sidefiler.")
    args = parser.parse_args(argv)
    try:
        if args.demo and args.input:
            raise ValueError("Velg enten --demo eller en inputfil.")
        if args.demo:
            source = DEMO
        elif args.input:
            source = Path(args.input)
        else:
            try:
                source = _discover_latest([Path("data/inbox")])
            except FileNotFoundError:
                source = DEMO
        if not source.is_file():
            raise ValueError(f"Filen finnes ikke: {source}. Kjør fra prosjektmappen eller oppgi en eksisterende fil.")
        demo = source.resolve() == DEMO.resolve()
        if demo:
            print("DEMO: syntetiske data, ikke observerte markedspriser.", file=sys.stderr)
        config_path = Path(args.config) if args.config else Path("config/demo-retail.toml" if demo else "config/report.toml")
        config = load_config(config_path if args.config or demo or config_path.exists() else None)
        output = Path(args.output) if args.output else Path("outputs") / ("demo/retail.xlsx" if demo else f"{source.stem}_innsiktsrapport.xlsx")
        if output.suffix.lower() != ".xlsx":
            raise ValueError("Rapportens målfil må slutte på .xlsx.")
        manifest = output.with_suffix(".json")
        notes = output.with_suffix(".notes.json")
        validate_outputs(source, [output, manifest, notes], overwrite=args.overwrite)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        result = analyze_file(source, config, source_url=args.source_url)
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError("Råfilen ble endret mens den ble lest. Kjør på et stabilt uttrekk.")
        result.summary.update(source_sha256=digest, settings=asdict(config), demo=demo)
        report = build_report(result, config, output)
        manifest.write_text(json.dumps(_json_value(result.summary), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        notes.write_text(json.dumps({"version": 1, "notes": header_note_specs(config)}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"input": str(source), "report": str(report), "manifest": str(manifest), "header_notes": str(notes), "demo": demo}, ensure_ascii=False))
        return 0
    except (ValueError, TypeError, OSError, ImportError) as error:
        parser.error(str(error))
