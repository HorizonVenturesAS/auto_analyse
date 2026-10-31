from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import AppConfig


REQUIRED_COLUMNS = {
    "observed_at_utc",
    "scrape_run_id",
    "scraper_key",
    "retailer_name",
    "retailer_domain",
    "product_id",
    "gtin",
    "product_brand",
    "model",
    "catalogue_category",
    "price",
    "currency",
    "before_price",
    "availability_status",
    "retailer_product_reference",
}


@dataclass
class AnalysisResult:
    summary: dict[str, Any]
    category_position: pd.DataFrame
    competitor_position: pd.DataFrame
    price_opportunities: pd.DataFrame
    availability_risks: pd.DataFrame
    underpricing_watch: pd.DataFrame
    quality_profile: pd.DataFrame


def _normalize_domain(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"^https?://", "", regex=True)
        .str.replace(r"^www\.", "", regex=True)
        .str.rstrip("/")
    )


def _read_source(path: Path) -> pd.DataFrame:
    suffixes = "".join(path.suffixes).lower()
    dtype = {"product_id": "string", "gtin": "string"}
    if suffixes.endswith((".csv", ".csv.gz", ".zip")):
        return pd.read_csv(path, low_memory=False, dtype=dtype, compression="infer")
    if suffixes.endswith(".xlsx"):
        with pd.ExcelFile(path) as workbook:
            matches = [
                name
                for name in workbook.sheet_names
                if REQUIRED_COLUMNS.issubset(pd.read_excel(workbook, sheet_name=name, nrows=0).columns)
            ]
            if len(matches) > 1:
                raise ValueError(
                    "Flere Excel-faner har alle obligatoriske råkolonner: "
                    + ", ".join(matches)
                    + ". Oppgi en råfil med én entydig datafane."
                )
            # Preserve the missing-column diagnostic for incompatible workbooks.
            sheet = matches[0] if matches else workbook.sheet_names[0]
            return pd.read_excel(workbook, sheet_name=sheet, dtype=dtype)
    raise ValueError(f"Ustøttet filtype: {path.name}. Bruk CSV, CSV.GZ, ZIP eller XLSX.")


def _mean_or_nan(series: pd.Series) -> float:
    return float(series.mean()) if len(series) else float("nan")


def analyze_file(
    source_path: str | Path,
    config: AppConfig,
    *,
    source_url: str | None = None,
) -> AnalysisResult:
    """Calculate the standard price, availability, competitor, and action metrics."""
    source = Path(source_path)
    df = _read_source(source)
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError("Råfilen mangler obligatoriske kolonner: " + ", ".join(missing))

    df["observed_at_utc"] = pd.to_datetime(
        df["observed_at_utc"], format="mixed", errors="coerce", utc=True
    ).dt.tz_convert(None)
    if df["observed_at_utc"].isna().all():
        raise ValueError("Ingen gyldige observed_at_utc-verdier ble funnet.")
    df["observed_date"] = df["observed_at_utc"].dt.normalize()

    text_columns = [
        "retailer_name",
        "retailer_domain",
        "catalogue_category",
        "availability_status",
        "product_brand",
        "model",
        "scraper_key",
        "currency",
        "retailer_product_reference",
    ]
    for column in text_columns:
        df[column] = df[column].astype("string").fillna("").astype(str).str.strip()
    df["retailer_domain_norm"] = _normalize_domain(df["retailer_domain"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    retailer = config.retailer
    monitoring = config.monitoring
    if not df["currency"].eq(monitoring.currency).all():
        raise ValueError(f"Råfilen må bare inneholde valuta {monitoring.currency}; tom eller annen valuta må avklares før analyse.")
    df["is_target"] = df["retailer_domain_norm"].eq(retailer.domain.lower()) | df[
        "scraper_key"
    ].eq(retailer.scraper_key)
    df["is_in_stock"] = df["availability_status"].eq(monitoring.in_stock_value)
    if not df["is_target"].any():
        raise ValueError(
            f"Fant ingen rader for {retailer.domain} eller scraper_key={retailer.scraper_key}."
        )

    raw_rows = len(df)
    run_key = ["scrape_run_id", "product_id", "retailer_domain_norm"]
    prisradar_dates = sorted(
        df.loc[
            df["scraper_key"].eq(monitoring.competitor_scraper_key), "observed_date"
        ].dropna().unique()
    )
    target_dates = sorted(df.loc[df["is_target"], "observed_date"].dropna().unique())
    missing_prisradar_dates = sorted(set(target_dates) - set(prisradar_dates))

    quality_profile = pd.DataFrame(
        [
            ["Rader i råfil", raw_rows, "Informasjon"],
            ["Kalenderdager", int(df["observed_date"].nunique()), "Informasjon"],
            [
                f"Unike {retailer.name}-produkter",
                int(df.loc[df["is_target"], "product_id"].nunique()),
                "Informasjon",
            ],
            ["GTIN-dekning", float(df["gtin"].notna().mean()), "Lav risiko"],
            ["Pris-dekning", float(df["price"].notna().mean()), "Lav risiko"],
            [
                "Tilgjengelighetsdekning",
                float(df["availability_status"].ne("").mean()),
                "Lav risiko",
            ],
            [
                "Førpris-dekning",
                float(df["before_price"].notna().mean()),
                "Begrenser kampanjeanalyse",
            ],
            ["Eksakte duplikatrader", int(df.duplicated().sum()), "Lav risiko"],
            [
                "Rader i dupliserte run/product/domain-grupper",
                int(df.duplicated(run_key, keep=False).sum()),
                "Laveste tilgjengelige tilbud brukes",
            ],
            [
                "Pris-konfliktgrupper i samme run/product/domain",
                int(df.groupby(run_key, dropna=False)["price"].nunique(dropna=True).gt(1).sum()),
                "Laveste pris brukes",
            ],
            ["Ugyldige priser (<=0)", int(df["price"].le(0).sum()), "Lav risiko"],
            [
                f"Ikke-{monitoring.currency}-rader",
                int(df["currency"].ne(monitoring.currency).sum()),
                "Kontroller valuta før bruk",
            ],
            [
                "Prisradar-dager",
                len(prisradar_dates),
                f"Mangler {len(missing_prisradar_dates)} av {len(target_dates)} måldager",
            ],
        ],
        columns=["kontroll", "verdi", "vurdering"],
    )

    target = (
        df[df["is_target"]]
        .sort_values("observed_at_utc")
        .drop_duplicates(["observed_date", "product_id"], keep="last")[
            [
                "observed_date",
                "product_id",
                "gtin",
                "product_brand",
                "model",
                "catalogue_category",
                "price",
                "availability_status",
                "is_in_stock",
                "retailer_product_reference",
            ]
        ]
        .rename(
            columns={
                "price": "own_price",
                "availability_status": "own_availability",
                "is_in_stock": "own_in_stock",
                "retailer_product_reference": "own_url",
            }
        )
    )

    competitor_raw = df[~df["is_target"]].copy()
    competitor_raw["available_price"] = competitor_raw["price"].where(
        competitor_raw["is_in_stock"]
    )
    competitor_daily = (
        competitor_raw.groupby(
            ["observed_date", "product_id", "retailer_domain_norm"],
            as_index=False,
            dropna=False,
        )
        .agg(
            retailer_name=("retailer_name", "last"),
            any_price=("price", "min"),
            available_price=("available_price", "min"),
            competitor_in_stock=("is_in_stock", "max"),
            competitor_url=("retailer_product_reference", "last"),
            observations=("price", "size"),
        )
    )

    market_base = (
        competitor_daily.groupby(["observed_date", "product_id"], as_index=False)
        .agg(
            competitor_domains_seen=("retailer_domain_norm", "nunique"),
            competitor_in_stock_count=("competitor_in_stock", "sum"),
        )
    )
    available = competitor_daily[
        competitor_daily["competitor_in_stock"]
        & competitor_daily["available_price"].notna()
    ].copy()
    market_prices = (
        available.groupby(["observed_date", "product_id"], as_index=False)
        .agg(
            best_comp_price=("available_price", "min"),
            median_comp_price=("available_price", "median"),
        )
    )
    best_rows = (
        available.sort_values(
            ["observed_date", "product_id", "available_price", "retailer_domain_norm"]
        )
        .drop_duplicates(["observed_date", "product_id"], keep="first")
        [["observed_date", "product_id", "retailer_name", "competitor_url"]]
        .rename(
            columns={
                "retailer_name": "best_competitor",
                "competitor_url": "best_competitor_url",
            }
        )
    )
    market = market_base.merge(
        market_prices, on=["observed_date", "product_id"], how="left"
    ).merge(best_rows, on=["observed_date", "product_id"], how="left")

    panel = target.merge(market, on=["observed_date", "product_id"], how="left")
    panel["competitor_domains_seen"] = panel["competitor_domains_seen"].fillna(0)
    panel["competitor_in_stock_count"] = panel["competitor_in_stock_count"].fillna(0)
    panel["has_competitor"] = panel["competitor_domains_seen"].gt(0)
    panel["competitor_available"] = panel["competitor_in_stock_count"].gt(0)
    panel["comparable_in_stock"] = panel["own_in_stock"] & panel["competitor_available"]
    panel["gap_to_min_pct"] = np.where(
        panel["comparable_in_stock"],
        panel["own_price"] / panel["best_comp_price"] - 1,
        np.nan,
    )
    panel["gap_to_median_pct"] = np.where(
        panel["comparable_in_stock"],
        panel["own_price"] / panel["median_comp_price"] - 1,
        np.nan,
    )
    panel["gap_to_min_nok"] = np.where(
        panel["comparable_in_stock"],
        panel["own_price"] - panel["best_comp_price"],
        np.nan,
    )
    panel["price_leader_1pct"] = panel["comparable_in_stock"] & panel[
        "gap_to_min_pct"
    ].le(monitoring.price_leader_tolerance)
    panel["above_5pct"] = panel["comparable_in_stock"] & panel["gap_to_min_pct"].gt(
        monitoring.price_alert_threshold
    )
    panel["above_15pct"] = panel["comparable_in_stock"] & panel["gap_to_min_pct"].gt(
        monitoring.critical_price_alert_threshold
    )
    panel["below_market_5pct"] = panel["comparable_in_stock"] & panel[
        "gap_to_min_pct"
    ].lt(monitoring.underpricing_threshold)
    panel["availability_risk"] = (~panel["own_in_stock"]) & panel[
        "competitor_available"
    ]

    latest_date = panel["observed_date"].max()
    latest = panel[panel["observed_date"].eq(latest_date)].copy()
    latest_comp = competitor_daily[
        competitor_daily["observed_date"].eq(latest_date)
    ].copy()
    latest_target = latest[
        ["product_id", "own_price", "own_in_stock", "catalogue_category"]
    ].copy()

    category_rows: list[dict[str, Any]] = []
    for category, group in latest.groupby("catalogue_category", dropna=False):
        comparable = group[group["comparable_in_stock"]]
        category_rows.append(
            {
                "catalogue_category": category,
                "products": int(group["product_id"].nunique()),
                "matched_products": int(group["has_competitor"].sum()),
                "match_rate": float(group["has_competitor"].mean()),
                "comparable_in_stock": int(group["comparable_in_stock"].sum()),
                "own_stock_rate": float(group["own_in_stock"].mean()),
                "competitor_stock_coverage": float(group["competitor_available"].mean()),
                "price_leader_share": _mean_or_nan(comparable["price_leader_1pct"]),
                "above_5pct_share": _mean_or_nan(comparable["above_5pct"]),
                "above_15pct_share": _mean_or_nan(comparable["above_15pct"]),
                "median_gap_to_cheapest": float(comparable["gap_to_min_pct"].median()),
                "price_opportunities": int(group["above_5pct"].sum()),
                "availability_risks": int(group["availability_risk"].sum()),
            }
        )
    category_position = pd.DataFrame(category_rows).sort_values(
        ["price_opportunities", "availability_risks"], ascending=False
    )

    competitor_overlap = latest_comp.merge(latest_target, on="product_id", how="inner")
    competitor_overlap["comparable"] = (
        competitor_overlap["competitor_in_stock"]
        & competitor_overlap["own_in_stock"]
        & competitor_overlap["available_price"].notna()
    )
    competitor_overlap["comp_gap_vs_own"] = np.where(
        competitor_overlap["comparable"],
        competitor_overlap["available_price"] / competitor_overlap["own_price"] - 1,
        np.nan,
    )
    competitor_overlap["competitor_cheaper"] = competitor_overlap["comparable"] & (
        competitor_overlap["available_price"]
        < competitor_overlap["own_price"] * (1 - monitoring.price_leader_tolerance)
    )
    competitor_overlap["own_cheaper"] = competitor_overlap["comparable"] & (
        competitor_overlap["available_price"]
        > competitor_overlap["own_price"] * (1 + monitoring.price_leader_tolerance)
    )

    competitor_rows: list[dict[str, Any]] = []
    for (domain, name), group in competitor_overlap.groupby(
        ["retailer_domain_norm", "retailer_name"], dropna=False
    ):
        comparable = group[group["comparable"]]
        competitor_rows.append(
            {
                "retailer_domain_norm": domain,
                "retailer_name": name,
                "matched_products": int(group["product_id"].nunique()),
                "in_stock_matches": int(group["competitor_in_stock"].sum()),
                "comparable_in_stock": int(group["comparable"].sum()),
                "competitor_cheaper_share": _mean_or_nan(comparable["competitor_cheaper"]),
                "own_cheaper_share": _mean_or_nan(comparable["own_cheaper"]),
                "median_comp_price_gap": float(comparable["comp_gap_vs_own"].median()),
            }
        )
    competitor_position = pd.DataFrame(competitor_rows).sort_values(
        "matched_products", ascending=False
    )

    own_change = target.groupby("product_id").agg(
        price_values=("own_price", "nunique"),
        availability_values=("own_availability", "nunique"),
    )
    own_price_changed_products = int(own_change["price_values"].gt(1).sum())
    own_availability_changed_products = int(
        own_change["availability_values"].gt(1).sum()
    )
    prisradar_date_set = set(pd.to_datetime(prisradar_dates))
    market_change = (
        panel[
            panel["competitor_available"]
            & panel["observed_date"].isin(prisradar_date_set)
        ]
        .groupby("product_id")
        .agg(
            best_price_values=("best_comp_price", "nunique"),
            best_competitor_values=("best_competitor", "nunique"),
        )
    )
    competitor_best_price_changed_products = int(
        market_change["best_price_values"].gt(1).sum()
    )
    best_competitor_changed_products = int(
        market_change["best_competitor_values"].gt(1).sum()
    )

    action_columns = [
        "product_id",
        "gtin",
        "product_brand",
        "model",
        "catalogue_category",
        "own_price",
        "own_availability",
        "best_comp_price",
        "best_competitor",
        "gap_to_min_nok",
        "gap_to_min_pct",
        "competitor_in_stock_count",
        "own_url",
        "best_competitor_url",
    ]
    price_opportunities = latest[latest["above_5pct"]][action_columns].sort_values(
        ["gap_to_min_nok", "gap_to_min_pct"], ascending=False
    )
    availability_risks = latest[latest["availability_risk"]][action_columns].sort_values(
        ["catalogue_category", "own_price"], ascending=[True, False]
    )
    underpricing_watch = latest[latest["below_market_5pct"]][action_columns].sort_values(
        "gap_to_min_pct"
    )

    comparable = latest[latest["comparable_in_stock"]]
    top_risk_category = (
        category_position.sort_values("availability_risks", ascending=False).iloc[0]
        if len(category_position)
        else None
    )
    summary = {
        "source_file": source.name,
        "source_url": source_url or "",
        "period_start": df["observed_date"].min().strftime("%Y-%m-%d"),
        "period_end": df["observed_date"].max().strftime("%Y-%m-%d"),
        "latest_date": latest_date.strftime("%Y-%m-%d"),
        "raw_rows": raw_rows,
        "target_products": int(latest["product_id"].nunique()),
        "matched_products": int(latest["has_competitor"].sum()),
        "match_rate": float(latest["has_competitor"].mean()),
        "comparable_in_stock": int(latest["comparable_in_stock"].sum()),
        "own_stock_rate": float(latest["own_in_stock"].mean()),
        "competitor_stock_coverage": float(latest["competitor_available"].mean()),
        "price_leader_share": _mean_or_nan(comparable["price_leader_1pct"]),
        "above_5pct_count": int(latest["above_5pct"].sum()),
        "above_5pct_share": _mean_or_nan(comparable["above_5pct"]),
        "above_15pct_count": int(latest["above_15pct"].sum()),
        "above_15pct_share": _mean_or_nan(comparable["above_15pct"]),
        "median_gap_to_cheapest": float(comparable["gap_to_min_pct"].median()),
        "median_gap_to_market": float(comparable["gap_to_median_pct"].median()),
        "availability_risk_count": int(latest["availability_risk"].sum()),
        "underpricing_watch_count": int(latest["below_market_5pct"].sum()),
        "listed_unit_gap_nok": float(
            latest.loc[latest["above_5pct"], "gap_to_min_nok"].clip(lower=0).sum()
        ),
        "own_price_changed_products": own_price_changed_products,
        "own_availability_changed_products": own_availability_changed_products,
        "competitor_best_price_changed_products": competitor_best_price_changed_products,
        "best_competitor_changed_products": best_competitor_changed_products,
        "prisradar_days": len(prisradar_dates),
        "missing_prisradar_dates": [
            pd.Timestamp(value).strftime("%Y-%m-%d") for value in missing_prisradar_dates
        ],
        "before_price_coverage": float(df["before_price"].notna().mean()),
        "availability_coverage": float(df["availability_status"].ne("").mean()),
        "top_risk_category": ""
        if top_risk_category is None
        else str(top_risk_category["catalogue_category"]),
        "top_risk_category_count": 0
        if top_risk_category is None
        else int(top_risk_category["availability_risks"]),
    }

    return AnalysisResult(
        summary=summary,
        category_position=category_position.reset_index(drop=True),
        competitor_position=competitor_position.reset_index(drop=True),
        price_opportunities=price_opportunities.reset_index(drop=True),
        availability_risks=availability_risks.reset_index(drop=True),
        underpricing_watch=underpricing_watch.reset_index(drop=True),
        quality_profile=quality_profile,
    )
