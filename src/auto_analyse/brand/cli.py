from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re

from .analysis import analyze_file
from .config import load_config
from .report import build_report, header_note_specs
from ..io_utils import validate_outputs


def discover_latest(directory: Path = Path("data/inbox/brands")) -> Path:
    # Intentionally does not look in the retail inbox or retail examples.
    candidates = [p for pattern in ("*.xlsx", "*.csv", "*.csv.gz", "*.zip") for p in directory.glob(pattern) if p.is_file() and not p.name.startswith("~$")]
    if not candidates:
        raise ValueError("Fant ingen brandråfil. Oppgi fil eller legg den i data/inbox/brands/.")
    return max(candidates, key=lambda p: (p.stat().st_mtime_ns, p.name))


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lag separate brandrapporter, én Excel-fil per leverandør.")
    parser.add_argument("input", nargs="?", help="CSV/CSV.GZ/ZIP/XLSX. Standard: nyeste fil i data/inbox/brands/.")
    parser.add_argument("--config", help="Egen TOML-konfigurasjon; uten argument brukes brandmodulens innebygde standarder.")
    parser.add_argument("--supplier", help="Valgfritt leverandørdomene eller leverandør-URL.")
    parser.add_argument("--output-dir", help="Målmappe. Standard: outputs/brands/<kildefil>-<kildehash>-<konfigurasjonshash>/")
    parser.add_argument("--overwrite", action="store_true", help="Tillat eksplisitt overskriving av tidligere brandrapporter i målgruppen.")
    parser.add_argument("--demo", action="store_true", help="Bruk syntetiske data fra examples/demo/brands.csv.")
    parser.add_argument("--name-suffix", default="", help="Valgfritt navnesuffiks, for eksempel _v2. Gjelder arbeidsbok og sidefiler.")
    parser.add_argument("--evidence-manifest", help="SHA-bundet kilde- og butikkbevis per tilbud. Source viser kildepriser med separat kontrollstatus; strict krever butikkbevis.")
    args = parser.parse_args(argv)
    try:
        if args.name_suffix and not re.fullmatch(r"_[A-Za-z0-9_-]{1,32}", args.name_suffix):
            raise ValueError("Navnesuffiks må starte med _ og inneholde 1–32 bokstaver, tall, _ eller -.")
        if args.demo and args.input:
            raise ValueError("Velg enten --demo eller en inputfil.")
        source = Path("examples/demo/brands.csv") if args.demo else Path(args.input) if args.input else discover_latest()
        if not source.is_file():
            raise ValueError(f"Filen finnes ikke: {source}")
        demo = source.resolve() == Path("examples/demo/brands.csv").resolve()
        config = load_config(args.config or ("config/demo-brand.toml" if demo else None))
        digest = _digest(source)
        settings_digest = hashlib.sha256(json.dumps(asdict(config), sort_keys=True).encode()).hexdigest()[:8]
        if args.demo and args.evidence_manifest:
            raise ValueError("Syntetisk demo skal ikke bruke ekte prisbevis.")
        results = analyze_file(source, config, supplier=args.supplier,
                               evidence_manifest=args.evidence_manifest, allow_synthetic=args.demo)
        if _digest(source) != digest:
            raise ValueError("Råfilen ble endret mens den ble lest. Kjør på et stabilt uttrekk.")
        stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", source.stem)[:80]
        output_dir = Path(args.output_dir) if args.output_dir else Path("outputs/demo/brands") if demo else Path("outputs/brands") / f"{stem}-{digest[:8]}-{settings_digest}"
        planned = []
        for result in results:
            supplier = result.summary["supplier"]
            slug = re.sub(r"[^a-z0-9.-]+", "-", supplier)[:80].strip(".-") or "leverandor"
            tag = hashlib.sha256(supplier.encode()).hexdigest()[:8]
            report = output_dir / f"brandinnsikt-{slug}-{tag}{args.name_suffix}.xlsx"
            paths = {"report": report, "manifest": report.with_suffix(".json"), "header_notes": report.with_suffix(".notes.json"), "observations": report.with_suffix(".observations.jsonl")}
            validate_outputs(source, list(paths.values()), overwrite=args.overwrite)
            planned.append((result, paths))
        output_dir.mkdir(parents=True, exist_ok=True)
        exports = []
        for result, paths in planned:
            result.summary["source_sha256"] = digest
            result.summary["demo"] = demo
            result.summary["output_files"] = {key: str(path.resolve()) for key, path in paths.items()}
            build_report(result, config, paths["report"])
            paths["manifest"].write_text(json.dumps(result.summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            paths["header_notes"].write_text(json.dumps({"version": 1, "notes": header_note_specs()}, ensure_ascii=False, indent=2), encoding="utf-8")
            result.observations.to_json(paths["observations"], orient="records", lines=True, force_ascii=False, date_format="iso")
            exports.append({"supplier": result.summary["supplier"], **{k: str(v.resolve()) for k, v in paths.items()}})
        print(json.dumps({"input": str(source.resolve()), "report_type": "brand", "demo": demo, "reports": exports}, ensure_ascii=False))
        return 0
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
