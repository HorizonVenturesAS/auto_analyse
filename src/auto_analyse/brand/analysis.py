from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import defaultdict
from pathlib import Path
from statistics import median
from urllib.parse import urlsplit
import math
import re
import unicodedata

import pandas as pd

from .config import BrandConfig
from .variants import assess_variant
from .evidence import PriceEvidence
import json


REQUIRED_COLUMNS = {
    "supplier", "requested_brand", "product_id", "title", "brand", "category",
    "retailer", "offer_id", "price", "currency", "availability", "observed_at",
    "is_used", "is_stale",
}
TEXT_COLUMNS = [
    "supplier", "requested_brand", "product_id", "title", "brand", "category", "gtin",
    "retailer", "offer_id", "currency", "availability", "prisradar_url", "retailer_url",
    "offer_title", "size", "color", "product_status", "price_qualifier", "review_reason",
    "model", "offer_model", "offer_gtin", "product_attributes", "offer_attributes", "offer_review_reason",
]
PRODUCT_KEY = ["supplier_key", "brand_key", "product_id"]
NA = "Ikke beregnbart"


@dataclass
class BrandResult:
    summary: dict
    brands: pd.DataFrame
    categories: pd.DataFrame
    retailers: pd.DataFrame
    products: pd.DataFrame
    availability: pd.DataFrame
    campaigns: pd.DataFrame
    observations: pd.DataFrame


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(c for c in value if c.isalnum() and not unicodedata.combining(c))


def normalize_domain(value: str) -> str:
    value = str(value).strip().lower()
    if not value:
        return ""
    parsed = urlsplit(value if "://" in value else "//" + value)
    return (parsed.hostname or value).removeprefix("www.").rstrip(".")


def _bool(value):
    if pd.isna(value) or str(value).strip() == "":
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "1.0"}:
        return True
    if text in {"false", "0", "0.0"}:
        return False
    return None


def read_source(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    identifiers = {c: "string" for c in ("product_id", "gtin", "offer_gtin", "offer_id", "retailer_id", "brand_id")}
    if path.suffix.lower() == ".xlsx":
        with pd.ExcelFile(path, engine="openpyxl") as wb:
            matches = [s for s in wb.sheet_names if REQUIRED_COLUMNS <= set(pd.read_excel(wb, sheet_name=s, nrows=0).columns)]
            if len(matches) > 1:
                raise ValueError("Flere Excel-faner har brandrådata: " + ", ".join(matches))
            if not matches:
                diagnostics = [s + ": " + ", ".join(sorted(REQUIRED_COLUMNS - set(pd.read_excel(wb, sheet_name=s, nrows=0).columns))) for s in wb.sheet_names]
                raise ValueError("Mangler obligatoriske brandkolonner. " + " | ".join(diagnostics))
            frame = pd.read_excel(wb, sheet_name=matches[0], dtype=identifiers)
    elif "".join(path.suffixes).lower().endswith((".csv", ".csv.gz", ".zip")):
        frame = pd.read_csv(path, dtype=identifiers, low_memory=False, compression="infer")
    else:
        raise ValueError("Brandanalysen støtter CSV, CSV.GZ, ZIP med én CSV, og XLSX.")
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("Mangler obligatoriske brandkolonner: " + ", ".join(sorted(missing)))
    if frame.empty:
        raise ValueError("Branduttrekket er tomt.")
    return frame


def _size(value: str, *, trailing: bool = False) -> float | None:
    value = str(value).casefold().replace(",", ".").replace("½", " 1/2")
    patterns = [r"(?:str\.?|størrelse|size)\s*(\d{1,3}(?:\.\d|\s+1/2)?)\b", r"\b(\d{1,3}(?:\.\d|\s+1/2)?)\s*eu\b"]
    if trailing:
        patterns += [r"(?:^|\s|-)\s*(\d{1,2}(?:\.\d|\s+1/2)?)\s*$"]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            token = match[1]
            return float(token.split()[0]) + .5 if "1/2" in token else float(token)
    return None


def _variant_conflict(row) -> bool:
    # Deliberately narrow: explicit size evidence, no fuzzy product matching.
    offer_size = _size(row.offer_title)
    if offer_size is None:
        return False
    raw_size = str(row.size).replace(",", ".")
    expected = float(raw_size) if re.fullmatch(r"\d{1,3}(?:\.\d)?", raw_size) else None
    if expected is None:
        footwear = bool(re.search(r"sko|shoe|boot|sandal|hansk", row.category + " " + row.title, re.I))
        expected = _size(row.title, trailing=footwear)
    return expected is not None and expected != offer_size


def _median(values):
    finite = [float(value) for value in values if value is not None and pd.notna(value)]
    return float(median(finite)) if finite else None


def _prepare(frame: pd.DataFrame, config: BrandConfig, *, evidence=None, synthetic=False) -> pd.DataFrame:
    d = frame.copy()
    if any(str(c).startswith("audit_") for c in d.columns):
        raise ValueError("Kolonnenavn med audit_-prefiks er reservert for sporbarhet.")
    d["audit_source_row"] = range(2, len(d) + 2)
    for c in TEXT_COLUMNS:
        if c not in d:
            d[c] = ""
        d[c] = d[c].astype("string").fillna("").astype(str).str.strip()
    for c in ("product_id", "gtin", "offer_id"):
        d[c] = d[c].str.replace(r"^(\d+)\.0$", r"\1", regex=True)
    for c in ("price", "regular_price", "shipping", "club_price", "bf_price"):
        if c not in d:
            d[c] = float("nan")
        d[c] = pd.to_numeric(d[c], errors="coerce")
    for c in ("supplier", "requested_brand", "product_id"):
        if d[c].eq("").any():
            raise ValueError(f"{c} mangler på {int(d[c].eq('').sum())} rader.")
    d["audit_observed_utc"] = pd.to_datetime(d.observed_at, errors="coerce", utc=True, format="mixed")
    if d.audit_observed_utc.isna().any():
        raise ValueError("Ugyldig eller manglende observed_at. Alle rader må ha et tidspunkt med UTC/offset.")
    # Naive dates are ambiguous: do not silently assume local/UTC.
    if not d.observed_at.astype(str).str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", case=False, regex=True).all():
        raise ValueError("observed_at må ha eksplisitt tidssone (Z eller UTC-offset).")
    d["supplier_key"] = d.supplier.map(normalize_domain)
    d["brand_key"] = d.requested_brand.map(normalize_name)
    d["shop"] = d.retailer.map(normalize_domain)
    if d.supplier_key.eq("").any() or d.brand_key.eq("").any():
        raise ValueError("Leverandør eller brand kan ikke normaliseres til en tom nøkkel.")
    aliases = {normalize_name(k): normalize_name(v) for k, v in config.brand_aliases.items()}
    d["audit_brand_mismatch"] = [normalize_name(actual) != aliases.get(key, key) for key, actual in zip(d.brand_key, d.brand)]
    d["audit_variant_conflict"] = [_variant_conflict(r) for r in d.itertuples()]
    variants = [assess_variant(r) for r in d.itertuples()]
    d["audit_offer_variant_status"] = [v["status"] for v in variants]
    d["audit_offer_variant_reasons"] = ["; ".join(v["reasons"]) for v in variants]
    d["audit_offer_variant_evidence"] = [json.dumps(v["evidence"], ensure_ascii=False, sort_keys=True) for v in variants]
    d["audit_variant_status"] = d["audit_offer_variant_status"]
    checks = ([{"source_consistency_status":"synthetic", "merchant_price_status":"synthetic",
                "stock_validation_status":"synthetic", "source_cache_status":"synthetic", "source_vat_basis":"synthetic",
                "price_context_status":"synthetic", "price_evidence_reason":"Explicitly authorized synthetic fixture"}] * len(d)
              if synthetic else [evidence.assess(row) for row in d.itertuples()])
    for key in ("source_consistency_status", "merchant_price_status", "stock_validation_status", "price_evidence_reason",
                "source_cache_status", "source_vat_basis", "price_context_status"):
        d["audit_" + key] = [check[key] for check in checks]
    d["audit_price_evidence_eligible"] = [synthetic or (
        check["source_consistency_status"] not in {"conflict", "invalid"}
        and check["merchant_price_status"] not in {"conflict", "invalid"}
        if config.price_evidence_mode == "source" else
        check["source_consistency_status"] == "verified" and check["merchant_price_status"] == "verified")
        for check in checks]
    d["audit_price_basis"] = ["synthetic" if synthetic else "independently_verified"
        if check["source_consistency_status"] == "verified" and check["merchant_price_status"] == "verified"
        else "source_observed" for check in checks]
    d["audit_product_variant_signature"] = [json.dumps(sorted({json.dumps(
        {k: c[k] for k in ("axis", "role", "value")}, ensure_ascii=False, sort_keys=True)
        for c in v["evidence"]["product_claims"]}), ensure_ascii=False) for v in variants]
    d["audit_used"] = d.is_used.map(_bool)
    d["audit_stale"] = d.is_stale.map(_bool)
    latest = d.groupby(PRODUCT_KEY).audit_observed_utc.transform("max")
    d["audit_selected_snapshot"] = d.audit_observed_utc.eq(latest)
    duplicate_fields = list(frame.columns)
    d["audit_exact_duplicate"] = d.duplicated(duplicate_fields)
    return d


def _aggregate(products: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    rows = []
    for key, group in products.groupby(keys, sort=True, dropna=False):
        values = key if isinstance(key, tuple) else (key,)
        stores = set().union(*group._shops)
        rows.append(dict(zip(keys, values)) | {
            "products": len(group), "stores": len(stores),
            "with_offers": int(group.offer_stores.gt(0).sum()),
            "stock_rate": float(group.stock_stores.gt(0).mean()),
            "comparable": int(group.comparable.sum()),
            "median_gap": _median(group.gap_pct),
            "single_stock": int(group.stock_stores.eq(1).sum()),
            "no_stock": int(group.stock_stores.eq(0).sum()),
            "review_products": int(group.review.ne("").sum()),
        })
    return pd.DataFrame(rows)


def _analyze_supplier(d: pd.DataFrame, config: BrandConfig, source: Path, as_of) -> BrandResult:
    selected = d[d.audit_selected_snapshot & ~d.audit_exact_duplicate].copy()
    labels = selected.groupby("brand_key").requested_brand.first().to_dict()
    # Duplicate GTINs are review candidates, never auto-merged across variants.
    gtin_products = selected[selected.gtin.ne("")].groupby("gtin").product_id.nunique()
    shared_gtins = set(gtin_products[gtin_products.gt(1)].index)
    products, listing_rows, campaign_rows, audit_reasons = [], [], [], {}
    selected_candidates, price_eligible = set(), set()
    groups = defaultdict(list)
    for row in selected.itertuples():
        groups[(row.supplier_key, row.brand_key, row.product_id)].append(row)

    def public_offer(row):
        return (pd.notna(row.price) and math.isfinite(row.price) and row.price > 0
                and row.currency == config.currency and row.audit_used == False
                and row.audit_stale == False and not row.price_qualifier
                and row.audit_offer_variant_status in {"compatible", "not_applicable"}
                and row.audit_price_evidence_eligible
                and not row.offer_review_reason)

    def lowest_per_shop(rows):
        chosen = {}
        for row in sorted(rows, key=lambda r: (r.price, r.offer_id, r.audit_source_row)):
            chosen.setdefault(row.shop, row)
        return chosen

    for (_, brand_key, product_id), g in sorted(groups.items()):
        first = g[0]
        brand = labels[brand_key]
        offers = [r for r in g if r.offer_id and r.shop]
        review = []
        if any(r.audit_brand_mismatch for r in g):
            review.append("Brandnavn må kontrolleres")
        if any(len({getattr(r, c) for r in g}) > 1 for c in ("gtin", "title", "size", "color", "brand", "category")):
            review.append("Motstridende produktmetadata")
        if len({r.audit_product_variant_signature for r in g}) > 1:
            review.append("Motstridende variantgrunnlag for samme produkt og snapshot")
        if {r.gtin for r in g} & shared_gtins:
            review.append("GTIN delt av flere produkt-ID-er")
        if any(r.audit_variant_conflict for r in g):
            review.append("Mulig størrelsesavvik")
        if any(r.review_reason for r in g):
            review.append("Kilden ber om kontroll")
        if any(_bool(getattr(r, "requires_id_lookup", False)) is True for r in g):
            review.append("Produkt-ID krever oppslag")
        if len({r.offer_id for r in offers}) < len(offers):
            review.append("Motstridende rader for samme tilbuds-ID")
        age = (as_of - first.audit_observed_utc).total_seconds() / 3600
        if age > config.max_snapshot_age_hours:
            review.append("For gammelt snapshot i forhold til uttrekket")

        stock_shops = {r.shop for r in offers if r.availability == config.in_stock_value}
        valid = [r for r in offers if public_offer(r) and r.availability == config.in_stock_value
                 and (r.audit_stock_validation_status != "conflict" if config.price_evidence_mode == "source"
                      else r.audit_stock_validation_status in {"verified", "synthetic"})]
        # Candidate prices are retained for inspection even for quarantined products.
        chosen = lowest_per_shop(valid)
        prices = [r.price for r in chosen.values()]
        low, high = (min(prices), max(prices)) if prices else (None, None)
        if len(prices) >= 2 and high / low > config.extreme_price_ratio:
            review.append("Ekstrem prisratio – kontroller pris og pakning")
        reason = "; ".join(review)
        variant_conflicts = sum(r.audit_offer_variant_status == "conflict" for r in offers)
        variant_unknown = sum(r.audit_offer_variant_status != "conflict" and
                              (r.audit_offer_variant_status == "unverified" or bool(r.offer_review_reason)) for r in offers)
        variant_note = (f"{variant_conflicts} feil variant; {variant_unknown} uavklart. Utelatt fra prisgrunnlaget."
                        if variant_conflicts or variant_unknown else "")
        comparable = len(prices) >= 2 and not reason
        chosen_indices = {r.Index for r in chosen.values()}
        selected_candidates.update(chosen_indices)
        if not reason:
            price_eligible.update(chosen_indices)
        metadata = {
            "brand": brand, "product_id": product_id, "gtin": first.gtin,
            "title": first.title, "category": first.category,
            "size": first.size, "color": first.color,
            "observed_at": first.audit_observed_utc.isoformat(),
            "prisradar_url": first.prisradar_url,
        }
        cheapest = ", ".join(sorted(r.shop for r in chosen.values() if r.price == low))
        expensive = ", ".join(sorted(r.shop for r in chosen.values() if r.price == high))
        products.append(metadata | {
            "brand_key": brand_key, "offer_stores": len({r.shop for r in offers}),
            "stock_stores": len(stock_shops), "price_stores": len(prices),
            "min_price": low, "median_price": _median(prices), "max_price": high,
            "gap_nok": high - low if comparable else None,
            "gap_pct": high / low - 1 if comparable else None,
            "cheapest": cheapest, "expensive": expensive, "comparable": comparable,
            "status": "Til kontroll" if reason else ("Sammenlignbart" if comparable else NA),
            "review": reason, "_shops": {r.shop for r in offers},
            "offer_review": variant_note,
            "price_evidence": ("Syntetisk demo" if config.price_evidence_mode == "synthetic" else
                f"{sum(r.audit_source_consistency_status == 'verified' for r in offers)}/{len(offers)} kildesamsvar; "
                f"{sum(r.audit_merchant_price_status == 'verified' for r in offers)}/{len(offers)} butikkpris; "
                f"{sum(r.audit_stock_validation_status == 'verified' for r in offers)}/{len(offers)} lager bekreftet. "
                "Se bevis og avvisningsårsaker per tilbud i observasjonsfilen."),
        })
        for row in g:
            flags = []
            if not row.offer_id or not row.shop:
                flags.append("Ingen identifiserbar butikk/tilbud")
            else:
                if not (pd.notna(row.price) and math.isfinite(row.price) and row.price > 0):
                    flags.append("Ugyldig pris")
                if row.currency != config.currency:
                    flags.append("Annen eller ukjent valuta")
                if row.availability != config.in_stock_value:
                    flags.append("Ikke registrert på lager")
                if row.audit_used != False:
                    flags.append("Brukt eller ukjent varetilstand")
                if row.audit_stale != False:
                    flags.append("Utdatert eller ukjent ferskhet")
                if row.price_qualifier:
                    flags.append("Pris med vilkår")
                if row.audit_offer_variant_status in {"conflict", "unverified"}:
                    flags.append("Tilbudsvariant: " + row.audit_offer_variant_reasons)
                if row.offer_review_reason:
                    flags.append("Tilbud krever kontroll: " + row.offer_review_reason)
                if not row.audit_price_evidence_eligible:
                    flags.append("Prisgrunnlag ikke verifisert: " + row.audit_price_evidence_reason)
                if config.price_evidence_mode == "source" and row.audit_stock_validation_status == "conflict":
                    flags.append("Motstridende lagerbevis")
                elif config.price_evidence_mode != "source" and row.audit_stock_validation_status not in {"verified", "synthetic"}:
                    flags.append("Lagerstatus kun kildeoppgitt eller uavklart")
                if not flags and row.Index not in chosen_indices:
                    flags.append("Annet tilbud valgt for samme produkt/butikk")
            if reason:
                flags.append(reason)
            audit_reasons[row.Index] = "; ".join(flags)

        shop_groups = defaultdict(list)
        for row in offers:
            shop_groups[row.shop].append(row)
        for shop, sg in sorted(shop_groups.items()):
            candidate = chosen.get(shop)
            other = [r.price for other_shop, r in chosen.items() if other_shop != shop]
            eligible = candidate is not None and not reason
            peer_gap = float(candidate.price / median(other) - 1) if eligible and len(other) >= config.min_peer_stores else None
            leader = float(candidate.price <= low * (1 + config.price_leader_tolerance)) if eligible and len(prices) >= 2 else None
            listing_rows.append(metadata | {
                "retailer": shop, "in_stock": shop in stock_shops,
                "availability": ", ".join(sorted({r.availability for r in sg})),
                "other_stock_stores": len(stock_shops - {shop}),
                "peer_gap": peer_gap, "leader": leader,
                "review": reason,
            })

        # Campaign unit: one lowest current public offer per product/store,
        # even if out of stock; missing before-price is not 'no campaign'.
        public = lowest_per_shop(r for r in offers if public_offer(r))
        for row in public.values():
            if pd.notna(row.regular_price) and math.isfinite(row.regular_price) and row.regular_price > row.price:
                campaign_rows.append(metadata | {
                    "retailer": row.shop, "offer_id": row.offer_id, "offer_title": row.offer_title,
                    "price": row.price, "regular_price": row.regular_price,
                    "discount": 1 - row.price / row.regular_price,
                    "availability": row.availability, "review": reason,
                    "retailer_url": row.retailer_url,
                })

    p = pd.DataFrame(products)
    listings = pd.DataFrame(listing_rows)
    campaign_columns = list(metadata) + ["retailer", "offer_id", "offer_title", "price", "regular_price", "discount", "availability", "review", "retailer_url"]
    campaigns = pd.DataFrame(campaign_rows, columns=campaign_columns)
    brands = _aggregate(p, ["brand"])
    categories = _aggregate(p, ["brand", "category"])
    retailer_rows = []
    if not listings.empty:
        for (brand, shop), group in listings.groupby(["brand", "retailer"], sort=True):
            brand_n = int(p.brand.eq(brand).sum())
            retailer_rows.append({
                "brand": brand, "retailer": shop, "products": len(group),
                "coverage": len(group) / brand_n, "stock_rate": float(group.in_stock.mean()),
                "price_products": int(group.leader.notna().sum()),
                "peer_products": int(group.peer_gap.notna().sum()),
                "peer_gap": _median(group.peer_gap), "leader_share": None if group.leader.notna().sum() == 0 else float(group.leader.mean()),
                "campaigns": int(((campaigns.brand == brand) & (campaigns.retailer == shop) & campaigns.review.eq("")).sum()),
                "stock_gaps": int((~group.in_stock & group.other_stock_stores.gt(0)).sum()),
            })
    retailers = pd.DataFrame(retailer_rows, columns=["brand", "retailer", "products", "coverage", "stock_rate", "price_products", "peer_products", "peer_gap", "leader_share", "campaigns", "stock_gaps"])
    availability_rows = []
    for row in p.itertuples():
        if row.offer_stores == 0:
            issue = "Ingen aktive tilbud"
        elif row.stock_stores == 0:
            issue = "Ingen butikk på lager"
        elif row.stock_stores == 1:
            issue = "Kun én butikk på lager"
        else:
            continue
        availability_rows.append({k: getattr(row, k) for k in metadata} | {
            "issue": issue, "retailer": "", "availability": "", "stock_stores": row.stock_stores,
            "review": row.review,
        })
    if not listings.empty:
        for row in listings[~listings.in_stock & listings.other_stock_stores.gt(0)].itertuples():
            availability_rows.append({k: getattr(row, k) for k in metadata} | {
                "issue": "Butikken mangler lager; andre har varen", "retailer": row.retailer,
                "availability": row.availability, "stock_stores": row.other_stock_stores,
                "review": row.review,
            })
    availability = pd.DataFrame(availability_rows, columns=list(metadata) + ["issue", "retailer", "availability", "stock_stores", "review"])
    audit = d.copy()
    audit["audit_selected_store_offer"] = audit.index.isin(selected_candidates)
    audit["audit_price_eligible"] = audit.index.isin(price_eligible)
    audit["audit_price_exclusion"] = [
        "Eldre snapshot" if not r.audit_selected_snapshot else
        "Eksakt duplikatrad" if r.audit_exact_duplicate else audit_reasons.get(r.Index, "")
        for r in audit.itertuples()
    ]
    offer_rows = selected[selected.offer_id.ne("") & selected.shop.ne("")]
    summary = {
        "report_type": "brand", "contract_version": 4,
        "supplier": str(d.supplier_key.iloc[0]), "supplier_sources": sorted(set(d.supplier)),
        "source_file": str(source.resolve()), "raw_rows": len(d), "selected_rows": len(selected),
        "period_start": selected.audit_observed_utc.min().isoformat(),
        "period_end": selected.audit_observed_utc.max().isoformat(),
        "snapshot_reference_time": as_of.isoformat(),
        "brands": int(p.brand.nunique()), "products": len(p),
        "stores": int(offer_rows.shop.nunique()), "offers": len(offer_rows),
        "with_offers": int(p.offer_stores.gt(0).sum()),
        "stock_rate": float(p.stock_stores.gt(0).mean()),
        "comparable": int(p.comparable.sum()),
        "candidate_comparable": int(p.price_stores.ge(2).sum()),
        "median_gap": _median(p.gap_pct),
        "single_stock": int(p.stock_stores.eq(1).sum()), "no_stock": int(p.stock_stores.eq(0).sum()),
        "review_products": int(p.review.ne("").sum()),
        "before_price_rows": int(offer_rows.regular_price.notna().sum()),
        "shipping_rows": int(offer_rows.shipping.notna().sum()),
        "retailer_url_rows": int(offer_rows.retailer_url.ne("").sum()),
        "variant_conflict_offers": int(offer_rows.audit_offer_variant_status.eq("conflict").sum()),
        "variant_unverified_offers": int((~offer_rows.audit_offer_variant_status.eq("conflict") &
            (offer_rows.audit_offer_variant_status.eq("unverified") | offer_rows.offer_review_reason.ne(""))).sum()),
        "products_with_variant_exclusions": int(p.offer_review.ne("").sum()),
        "source_consistency_counts": offer_rows.audit_source_consistency_status.value_counts().to_dict(),
        "merchant_price_counts": offer_rows.audit_merchant_price_status.value_counts().to_dict(),
        "stock_validation_counts": offer_rows.audit_stock_validation_status.value_counts().to_dict(),
        "source_cache_counts": offer_rows.audit_source_cache_status.value_counts().to_dict(),
        "source_vat_basis_counts": offer_rows.audit_source_vat_basis.value_counts().to_dict(),
        "price_evidence_verified_offers": int((offer_rows.audit_source_consistency_status.eq("verified") & offer_rows.audit_merchant_price_status.eq("verified")).sum()),
        "price_evidence_missing_offers": int((~(offer_rows.audit_source_consistency_status.eq("verified") & offer_rows.audit_merchant_price_status.eq("verified"))).sum()),
        "price_policy_excluded_offers": int((~offer_rows.audit_price_evidence_eligible).sum()),
        "independently_verified_stock_offers": int(offer_rows.audit_stock_validation_status.eq("verified").sum()),
        "source_reported_stock_offers": int(offer_rows.availability.eq(config.in_stock_value).sum()),
        "stock_basis": "source_reported; independently verified stock is counted separately",
        "release_status": ("synthetic" if config.price_evidence_mode == "synthetic" else "source_report" if config.price_evidence_mode == "source" else "verified" if len(offer_rows) > 0
            and offer_rows.audit_source_consistency_status.eq("verified").all()
            and offer_rows.audit_merchant_price_status.eq("verified").all()
            and offer_rows.audit_stock_validation_status.eq("verified").all()
            and offer_rows.audit_offer_variant_status.isin({"compatible", "not_applicable"}).all()
            else "provisional"),
        "settings": asdict(config),
    }
    return BrandResult(summary, brands, categories, retailers,
                       p.drop(columns=["_shops", "brand_key"]).sort_values(["brand", "gap_pct", "product_id"], ascending=[True, False, True], na_position="last"),
                       availability, campaigns, audit)


def analyze_file(source_path: str | Path, config: BrandConfig | None = None, *, supplier: str | None = None,
                 evidence_manifest: str | Path | None = None, allow_synthetic: bool = False) -> list[BrandResult]:
    config = config or BrandConfig()
    source = Path(source_path)
    if config.price_evidence_mode == "synthetic" and allow_synthetic is not True:
        raise ValueError("Synthetic price evidence requires explicit trusted caller authorization.")
    evidence = PriceEvidence(evidence_manifest, max_age_hours=config.max_evidence_age_hours,
                             max_source_cache_age_hours=config.max_source_cache_age_hours)
    d = _prepare(read_source(source), config, evidence=evidence,
                 synthetic=config.price_evidence_mode == "synthetic" and allow_synthetic is True)
    as_of = d.audit_observed_utc.max()
    if supplier:
        d = d[d.supplier_key.eq(normalize_domain(supplier))]
        if d.empty:
            raise ValueError(f"Fant ingen data for leverandør: {supplier}")
    results = [_analyze_supplier(group, config, source, as_of) for _, group in d.groupby("supplier_key", sort=True)]
    for result in results:
        result.summary["evidence_manifest_sha256"] = evidence.manifest_sha256
    return results
