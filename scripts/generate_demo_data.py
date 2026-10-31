"""Generate the small, entirely invented fixtures shipped with this project.

No network, database, customer file or random source is read.
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def csv_bytes(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def retail_rows() -> list[dict]:
    rows = []
    own_prices = [120, 104, 90, 100, 100, 200, 100, 150]
    peers = {1: [("alpha.example", 100)], 2: [("alpha.example", 100)],
             3: [("beta.example", 100)], 4: [("alpha.example", 80)],
             5: [("beta.example", 90)], 7: [("alpha.example", 100)],
             8: [("alpha.example", 100), ("beta.example", 120)]}
    for day in (1, 2):
        for product, price in enumerate(own_prices, start=1):
            row = {
                "observed_at_utc": f"2026-01-0{day}T12:00:00Z",
                "scrape_run_id": f"demo-day-{day}", "scraper_key": "demo_retail",
                "retailer_name": "Demobutikken", "retailer_domain": "demobutikk.example",
                "product_id": f"{product:06d}", "gtin": f"00000000{product:05d}",
                "product_brand": "Demo Nord", "model": f"Demoprodukt {product}",
                "catalogue_category": "Demo fliser" if product <= 4 else "Demo verktøy",
                "price": 110 if day == 1 and product == 1 else price,
                "currency": "NOK", "before_price": 130 if product == 2 else "",
                "availability_status": "out_of_stock" if day == 2 and product == 4 else "in_stock",
                "retailer_product_reference": f"https://demobutikk.example/produkt/{product}",
            }
            rows.append(row)
            for domain, peer_price in peers.get(product, []):
                rows.append({**row, "scraper_key": "demo_market", "retailer_name": domain,
                             "retailer_domain": domain, "price": peer_price + (10 if day == 1 and product == 8 else 0),
                             "before_price": "", "availability_status": "out_of_stock" if product == 5 else "in_stock",
                             "retailer_product_reference": f"https://{domain}/produkt/{product}"})
    return rows


def brand_rows() -> list[dict]:
    def offer(product, shop, price, **changes):
        return {
            "supplier": "demo-maker.example", "requested_brand": "Demo Nord",
            "product_id": product, "title": f"Demovare {product}", "brand": "Demo Nord",
            "category": "Demo hjem", "retailer": shop,
            "offer_id": f"{product}-{shop}" if shop else "", "price": price,
            "currency": "NOK", "availability": "in_stock" if shop else "",
            "observed_at": "2026-01-02T12:00:00Z", "is_used": False, "is_stale": False,
            "gtin": "00000000" + product.replace("p", "1").replace("q", "2").zfill(5),
            "regular_price": "", "shipping": "", "offer_title": f"Demovare {product}",
            "prisradar_url": f"https://catalogue.example/produkter/{product}",
            "retailer_url": f"https://{shop}/produkt/{product}" if shop else "", **changes,
        }
    rows = [offer("p1", "alpha.example", 100), offer("p1", "beta.example", 120, regular_price=150),
            offer("p1", "gamma.example", 140), offer("p2", "alpha.example", 80),
            offer("p3", "", ""), offer("p4", "alpha.example", 100),
            offer("p4", "beta.example", 90, availability="out_of_stock")]
    for product, price_a, price_b in (("q1", 200, 220), ("q2", 10, 100)):
        for shop, price in (("alpha.example", price_a), ("beta.example", price_b)):
            rows.append(offer(product, shop, price, supplier="demo-tools.example",
                              requested_brand="Demo Verk", brand="Demo Verk", category="Demo verktøy"))
    return rows


def demo_files() -> dict[str, bytes]:
    return {"examples/demo/retail.csv": csv_bytes(retail_rows()),
            "examples/demo/brands.csv": csv_bytes(brand_rows())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Kontroller at demoene er uendrede syntetiske data.")
    args = parser.parse_args()
    errors = []
    for relative, content in demo_files().items():
        path = ROOT / relative
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                errors.append(relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    if errors:
        parser.exit(1, "Demofiler avviker fra generatoren: " + ", ".join(errors) + "\n")
    print("Syntetiske demoer " + ("kontrollert." if args.check else "generert."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
