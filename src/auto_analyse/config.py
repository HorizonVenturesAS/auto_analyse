from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
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

    def __post_init__(self):
        for value in (self.retailer.name, self.retailer.domain, self.retailer.scraper_key,
                      self.monitoring.currency, self.monitoring.in_stock_value):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Butikk, domene, scraper-nøkkel, valuta og lagerstatus må være tekst.")
        m = self.monitoring
        for name in ("price_leader_tolerance", "price_alert_threshold", "critical_price_alert_threshold", "underpricing_threshold"):
            value = getattr(m, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} må være et endelig tall.")
        if not (0 <= m.price_leader_tolerance < 1 and 0 <= m.price_alert_threshold < m.critical_price_alert_threshold and -1 < m.underpricing_threshold < 0):
            raise ValueError("Ugyldige pristerskler: toleranse 0–1, kritisk > varsel >=0, marginvakt mellom -1 og 0.")


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load TOML overrides; defaults make the package usable without a config file."""
    if path is None:
        return AppConfig()
    config_path = Path(path)
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    unknown = set(raw) - {"retailer", "monitoring", "report"}
    if unknown:
        raise ValueError("Ukjente konfigurasjonsseksjoner: " + ", ".join(sorted(unknown)))

    return AppConfig(
        retailer=RetailerConfig(**raw.get("retailer", {})),
        monitoring=MonitoringConfig(**raw.get("monitoring", {})),
        report=ReportConfig(**raw.get("report", {})),
    )
