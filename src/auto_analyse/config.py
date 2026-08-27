from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class RetailerConfig:
    name: str = "Flisekompaniet"
    domain: str = "flisekompaniet.no"
    scraper_key: str = "flisekompaniet_no"


@dataclass(frozen=True)
class MonitoringConfig:
    competitor_scraper_key: str = "prisradar_no"
    in_stock_value: str = "in_stock"
    currency: str = "NOK"
    price_leader_tolerance: float = 0.01
    price_alert_threshold: float = 0.05
    critical_price_alert_threshold: float = 0.15
    underpricing_threshold: float = -0.05


@dataclass(frozen=True)
class ReportConfig:
    title: str = "Flisekompaniet: konkurranseinnsikt som kan gjøres handlingsbar"
    pilot_days: int = 30
    pilot_category_count: int = 5


@dataclass(frozen=True)
class AppConfig:
    retailer: RetailerConfig = RetailerConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    report: ReportConfig = ReportConfig()


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load TOML overrides; defaults make the package usable without a config file."""
    if path is None:
        return AppConfig()
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()

    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    return AppConfig(
        retailer=RetailerConfig(**raw.get("retailer", {})),
        monitoring=MonitoringConfig(**raw.get("monitoring", {})),
        report=ReportConfig(**raw.get("report", {})),
    )
