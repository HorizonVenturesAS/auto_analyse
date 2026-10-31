from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import tomllib


@dataclass(frozen=True)
class BrandConfig:
    currency: str = "NOK"
    in_stock_value: str = "in_stock"
    # Review rule, not a business target: quarantine a whole product's prices.
    extreme_price_ratio: float = 5.0
    price_leader_tolerance: float = 0.01
    min_peer_stores: int = 2
    max_snapshot_age_hours: float = 48.0
    title: str = "Brandinnsikt – pris og tilgjengelighet hos nettbutikkene"
    brand_aliases: dict[str, str] = field(default_factory=lambda: {
        "JRG": "Jrg Sanipex", "Structon": "Structron",
        "Power Adhesives": "Power Adhesive",
    })

    def __post_init__(self):
        for name in ("extreme_price_ratio", "price_leader_tolerance", "max_snapshot_age_hours"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} må være et endelig tall.")
        if self.extreme_price_ratio <= 1 or self.max_snapshot_age_hours <= 0:
            raise ValueError("Prisratio må være >1 og snapshot-alder >0.")
        if not 0 <= self.price_leader_tolerance < 1:
            raise ValueError("price_leader_tolerance må være mellom 0 og 1.")
        if type(self.min_peer_stores) is not int or self.min_peer_stores < 2:
            raise ValueError("min_peer_stores må være et heltall >=2.")
        if not self.currency.strip() or not self.in_stock_value.strip():
            raise ValueError("Valuta og lagerstatus kan ikke være tomme.")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in self.brand_aliases.items()):
            raise ValueError("Brandaliaser må være tekstpar.")


def load_config(path: str | Path | None = None) -> BrandConfig:
    if path is None:
        return BrandConfig()
    with Path(path).open("rb") as handle:
        raw = tomllib.load(handle)
    unknown = set(raw) - {"brand", "brand_aliases"}
    if unknown:
        raise ValueError("Ukjente konfigurasjonsseksjoner: " + ", ".join(sorted(unknown)))
    values = dict(raw.get("brand", {}))
    if "brand_aliases" in raw:
        values["brand_aliases"] = raw["brand_aliases"]
    return BrandConfig(**values)
