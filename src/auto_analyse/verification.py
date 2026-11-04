"""Build a reproducible review queue from the existing report analysis, offline."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random

from .io_utils import validate_outputs


def _records(frame):
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def build_plan(source: Path, mode: str, config=None, *, evidence_manifest=None,
               sample_size=10, seed=0, gap_threshold=0.5, demo=False):
    """Prioritize evidence work; never approve variants or recalculate report rules."""
    source = Path(source)
    if mode not in {"brand", "retail"}:
        raise ValueError("mode må være brand eller retail")
    if sample_size < 0 or not math.isfinite(gap_threshold) or gap_threshold < 0:
        raise ValueError("Utvalgsstørrelse og gapgrense må være ikke-negative")
    if evidence_manifest and mode != "brand":
        raise ValueError("Bevismanifest støttes bare for brand")
    if demo:
        expected = Path("examples/demo/brands.csv" if mode == "brand" else "examples/demo/retail.csv")
        if source.resolve() != expected.resolve():
            raise ValueError("Demo krever prosjektets syntetiske råfil")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    units = []
    summaries = []
    if mode == "brand":
        from .brand.analysis import analyze_file
        from .brand.analysis import normalize_name
        from .brand.config import load_config
        settings = load_config(config)
        for result in analyze_file(source, settings, evidence_manifest=evidence_manifest, allow_synthetic=demo):
            supplier = result.summary["supplier"]
            summaries.append({k: result.summary[k] for k in ("supplier", "products", "offers", "comparable", "period_start", "period_end")})
            observations = _records(result.observations)
            grouped_offers = defaultdict(list)
            for row in observations:
                if row.get('audit_selected_snapshot') and not row.get('audit_exact_duplicate'):
                    grouped_offers[(row['brand_key'], row['product_id'])].append(row)
            for product in _records(result.products):
                pid = product["product_id"]
                offers = grouped_offers[(normalize_name(product['brand']), pid)]
                flags = []
                if product["review"]: flags.append("product_review")
                if any(r.get("audit_offer_variant_status") == "conflict" or r.get("offer_review_status") == "conflict" for r in offers): flags.append("variant_conflict")
                if product["stock_stores"] >= 2 and not product["comparable"]: flags.append("blocked_comparison")
                if any(r.get("audit_offer_variant_status") == "unverified" or r.get("offer_review_reason") for r in offers): flags.append("unverified_offer")
                if product["offer_stores"] == 0: flags.append("no_source_offers")
                if product["stock_stores"] < 2: flags.append("insufficient_stock_stores")
                gap = product.get("gap_pct")
                if gap is not None and abs(gap) >= gap_threshold: flags.append("large_price_gap")
                units.append({"key": [supplier, product["brand"], pid], "product": product,
                              "offers": offers, "flags": flags})
    else:
        from .analysis import analyze_file, _read_source, _normalize_domain
        import pandas as pd
        from .config import load_config
        settings = load_config(config)
        result = analyze_file(source, settings)
        summaries.append({k: result.summary[k] for k in ("target_products", "comparable_in_stock", "period_start", "period_end", "latest_date")})
        # Alert tables intentionally omit ordinary products. Screen the entire
        # target assortment from the raw snapshot, not only the alert rows.
        raw = _read_source(source)
        stamps = pd.to_datetime(raw.observed_at_utc, format="mixed", errors="coerce", utc=True)
        raw = raw[stamps.dt.strftime('%Y-%m-%d').eq(result.summary['latest_date'])].copy()
        raw['_target'] = (_normalize_domain(raw.retailer_domain).eq(settings.retailer.domain.lower())
                          | raw.scraper_key.fillna('').astype(str).str.strip().eq(settings.retailer.scraper_key))
        alerts = {r['product_id']: r for r in _records(result.price_opportunities)}
        own_groups, peer_groups = defaultdict(list), defaultdict(list)
        for row in _records(raw):
            is_target = row.pop('_target')
            (own_groups if is_target else peer_groups)[row['product_id']].append(row)
        for pid, own in sorted(own_groups.items()):
            peers = peer_groups[pid]
            product = {'product_id': str(pid), 'model': own[-1]['model'], 'gtin': own[-1]['gtin'],
                       'category': own[-1]['catalogue_category'], 'report_alert': alerts.get(pid)}
            flags = []
            if any(not r.get('retailer_product_reference') for r in own + peers): flags.append('missing_product_reference')
            if not product['gtin']: flags.append('missing_identity')
            if len({r['gtin'] for r in own if r['gtin']}) > 1: flags.append('product_review')
            def priced(row):
                try: return math.isfinite(float(row['price'])) and float(row['price']) > 0
                except (TypeError, ValueError): return False
            if not any(priced(r) for r in own): flags.append('invalid_own_price')
            stocked = [r for r in peers if r['availability_status'] == settings.monitoring.in_stock_value]
            if not peers: flags.append('no_source_competitor')
            elif not stocked: flags.append('no_in_stock_competitor')
            elif not any(priced(r) for r in stocked): flags.append('no_usable_competitor_price')
            gap = (alerts.get(pid) or {}).get('gap_to_min_pct')
            if gap is not None and abs(gap) >= gap_threshold: flags.append("large_price_gap")
            units.append({"key": [str(pid)], "product": product, 'source_rows': own + peers, "flags": flags})
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ValueError("Råfilen endret seg under kontrollen")
    units.sort(key=lambda u: tuple(u["key"]))
    sample = set(random.Random(seed).sample(range(len(units)), min(sample_size, len(units))))
    for index, unit in enumerate(units):
        unit["random_sample"] = index in sample
        unit["review_required"] = bool(unit["flags"] or unit["random_sample"])
        unit["priority"] = (0 if any(f in unit["flags"] for f in ("variant_conflict", "product_review", "invalid_own_price"))
                            else 1 if "blocked_comparison" in unit["flags"] else 2 if unit["flags"] else 3)
    queue = sorted((u for u in units if u["review_required"]), key=lambda u: (u["priority"], tuple(u["key"])))
    return {"version": 1, "mode": mode, "source_file": str(source.resolve()), "source_sha256": digest,
            "settings": asdict(settings),
            "evidence_manifest": str(Path(evidence_manifest).resolve()) if evidence_manifest else None,
            "evidence_manifest_sha256": hashlib.sha256(Path(evidence_manifest).read_bytes()).hexdigest() if evidence_manifest else None,
            "demo": demo, "seed": seed, "sample_size": min(sample_size, len(units)),
            "gap_threshold": gap_threshold, "analysis": summaries, "products_screened": len(units),
            "review_queue_count": len(queue), "status": "review_pending",
            "scope": "Offline screening and review planning; no external verification or approval",
            "units": units, "queue": queue}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?")
    parser.add_argument("--mode", required=True, choices=("brand", "retail"))
    parser.add_argument("--config")
    parser.add_argument("--evidence-manifest")
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--gap-threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.demo and args.input: raise ValueError("Velg enten --demo eller input")
        if not args.demo and not args.input: raise ValueError("Oppgi råfil eller --demo")
        source = Path("examples/demo/brands.csv" if args.mode == "brand" else "examples/demo/retail.csv") if args.demo else Path(args.input)
        config = args.config
        if args.demo and not config:
            config = "config/demo-brand.toml" if args.mode == "brand" else "config/demo-retail.toml"
        if args.output.suffix.lower() != '.json': raise ValueError("Kontrollplanen må ha .json-endelse")
        validate_outputs(source, [args.output], overwrite=args.overwrite)
        for protected in (config, args.evidence_manifest):
            if protected: validate_outputs(Path(protected), [args.output], overwrite=args.overwrite)
        plan = build_plan(source, args.mode, config, evidence_manifest=args.evidence_manifest,
                          sample_size=args.sample_size, seed=args.seed, gap_threshold=args.gap_threshold, demo=args.demo)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(json.dumps({k: plan[k] for k in ("mode", "products_screened", "review_queue_count", "status")}, ensure_ascii=False))
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
