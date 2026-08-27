# Rapportkontrakt

Les denne referansen bare når beregninger, kolonner, terskler, råskjema eller layout skal endres.

## Rådatakrav

Obligatoriske kolonner:

`observed_at_utc`, `scrape_run_id`, `scraper_key`, `retailer_name`, `retailer_domain`, `product_id`, `gtin`, `product_brand`, `model`, `catalogue_category`, `price`, `currency`, `before_price`, `availability_status`, `retailer_product_reference`.

Standard målaktør er `retailer_domain = flisekompaniet.no` eller `scraper_key = flisekompaniet_no`. Konkurrentdata er alle øvrige rader. Standard sammenlignbar konkurrentkjøring har `scraper_key = prisradar_no`.

## Datagrain og matching

- Egen observasjon: siste rad per `observed_date + product_id`.
- Konkurrentobservasjon: én rad per `observed_date + product_id + retailer_domain_norm`.
- Ved flere konkurrenttilbud brukes laveste pris blant rader som er `in_stock`.
- Markedsminimum og markedsmedian beregnes over laveste tilgjengelige pris per konkurrentdomene.
- Et produkt er prissammenlignbart bare når både målaktøren og minst én konkurrent er `in_stock`.

## KPI-er

- Matchgrad = produkter med minst én konkurrentobservasjon / alle målprodukter.
- Prislederandel = andel sammenlignbare produkter der egen pris er høyst 1 % over billigste konkurrent.
- Prisvarsel >5 % = sammenlignbare produkter der `egen pris / beste konkurrentpris - 1 > 0,05`.
- Prisvarsel >15 % = samme beregning med terskel `0,15`.
- Median gap til billigste = medianen av `egen pris / beste konkurrentpris - 1` blant sammenlignbare produkter.
- Tilgjengelighetsrisiko = målaktøren er ikke `in_stock`, mens minst én konkurrent er `in_stock`.
- Marginvakt = sammenlignbare produkter der prisgapet er lavere enn `-0,05`.
- Pris- og prislederendringer teller produkter med mer enn én observert verdi i perioden; markedsendringer vurderes på dager med Prisradar-kjøring.

Tersklene er konfigurert i `config/report.toml`.

## Arbeidsbokkontrakt

Fane- og kolonnerekkefølge:

1. `Kategorier`: Produktkategori, Produkter, Matchede produkter, Matchgrad, Sammenlignbare in-stock, Egen lagerandel, Konkurrent lagerdekning, Prislederandel, Andel >5 % over billigste, Andel >15 % over billigste, Median gap til billigste, Prisvarsler, Tilgjengelighetsrisiko.
2. `Konkurrenter`: Konkurrentdomene, Matchede produkter, In-stock-matcher, Sammenlignbare in-stock, Konkurrent billigere, Flisekompaniet billigere, Median konkurrentgap.
3. `Prisvarsler`: standard produktlisten med 14 sporbare produkt-, pris-, status- og URL-kolonner.
4. `Tilgjengelighetsrisiko`: samme produktkolonner.
5. `Marginvakt`: samme produktkolonner.
6. `Analyse & oppsummering`: åtte KPI-kort, tolkning, pitch, neste steg, forbehold og innbakt måltallstabell.
7. `Kolonneforklaringer`: forklaring av alle synlige tabellkolonner.

Alle KPI-er skal være numeriske celler med lesbare formater: heltall `#,##0`, valuta `#,##0 "NOK"` og dashboard-prosenter `0%`. Det skal ikke finnes grafer, `#REF!`-feil, fanene `Utvikling`/`Datakvalitet` eller en separat `Måltall`-fane.

## Referanse og akseptanse

- Visuell referanse: `examples/reference/Flisekompaniet_konkurrentinnsikt_2026-08-20_revidert.xlsx`.
- Datagrunnlag: `examples/raw/flisekompaniet_category_extract_last_7_days_2026-08-20.zip`.
- `tests/test_example_report.py` inneholder akseptansetallene for eksempelperioden.
