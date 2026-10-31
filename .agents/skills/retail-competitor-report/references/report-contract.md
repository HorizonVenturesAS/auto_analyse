# Retailrapport – kontrakt

Kontrakten gjelder `auto_analyse`. [Brandmodulen](../../../../docs/brand-report-contract.md)
har eget skjema og egne beregninger.

## Input og konfigurasjon

Støttet: UTF-8 CSV, CSV.GZ, ZIP med én CSV og XLSX. Obligatoriske kolonner:

`observed_at_utc`, `scrape_run_id`, `scraper_key`, `retailer_name`,
`retailer_domain`, `product_id`, `gtin`, `product_brand`, `model`,
`catalogue_category`, `price`, `currency`, `before_price`,
`availability_status`, `retailer_product_reference`.

I Excel velges den eneste fanen med alle obligatoriske navn i første rad.
Flere kvalifiserende faner gir feil. Produkt-ID og GTIN leses som tekst.
CSV bruker komma og desimalpunktum. Råfilen endres ikke.

Standard målbutikk er `retailer_domain=flisekompaniet.no` eller
`scraper_key=flisekompaniet_no`. Andre rader er konkurrentobservasjoner.
Standard kilde for sammenlignbare konkurrentdager er `prisradar_no`.
Egne butikker bruker egen TOML. Butikknavn, valuta, lagerstatus og terskler skal
gjengis konsekvent i overskrifter, forklaringer, KPI-kort og notater.
Input skal bruke konfigurert valuta; ingen valutakonvertering gjøres.

Uten input velges nyeste støttede fil direkte i `data/inbox/`.
Demo kan aldri vinne over en innboksfil bare fordi den er nyere.
Tom innboks gir den tydelig merkede syntetiske demoen, med demokonfigurasjon.
`--demo` velger demo uttrykkelig. Låsefiler med `~$` ignoreres.

Uten `--config` leses `config/report.toml` hvis den finnes, ellers innebygde
standarder. Ved demo leses `config/demo-retail.toml`. En uttrykkelig angitt fil
som ikke finnes gir feil; ugyldige seksjoner og terskler avvises.

## Identitet og beregninger

- Egen observasjon: siste rad per UTC-dag + produkt-ID.
- Konkurrentobservasjon: én rad per dag + produkt-ID + normalisert butikkdomene.
- Flere tilgjengelige tilbud fra samme konkurrent: laveste pris brukes.
- Markedsminimum/median beregnes over tilgjengelig pris per konkurrentdomene.
- Sammenlignbarhet krever både målbutikk og minst én konkurrent på lager.
- **Produkt-ID må være en felles nøkkel fra innsamlingen.** GTIN er sporbarhet;
  analysen gjør ikke selv GTIN-oppslag eller matching av ulike butikk-SKU-er.
- Alle KPI-er bruker siste dag, med mindre de eksplisitt beskriver periodeendring.

Med standardkonfigurasjon:

| KPI | Definisjon |
|---|---|
| Matchgrad | Produkter med minst én konkurrentobservasjon / alle målprodukter |
| Prislederandel | Egen pris høyst 1 % over billigste tilgjengelige konkurrent, blant sammenlignbare |
| Varsel >5 % | Egen pris / billigste konkurrentpris - 1 > 0,05 |
| Kritisk >15 % | Samme forhold > 0,15 |
| Median prisgap | Median av prisforholdet blant sammenlignbare produkter |
| Tilgjengelighetsrisiko | Målbutikk ikke på lager, minst én konkurrent på lager |
| Marginvakt | Sammenlignbar egen pris mer enn 5 % under billigste konkurrent |

Konfigurasjonen styrer de faktiske tersklene. Interne JSON-/DataFrame-nøkler som
`above_5pct` og `gap_to_min_nok` beholdes for bakoverkompatibilitet selv om terskel
eller valuta endres. Manifestets `settings` viser hva som faktisk ble brukt.
Pris-/prislederendringer teller produkter med mer enn én observert verdi.
Markedsendringer vurderes på dager med konkurrentkjøring.

## Arbeidsbok

Fast fanerekkefølge:

1. Kategorier
2. Konkurrenter
3. Prisvarsler
4. Tilgjengelighetsrisiko
5. Marginvakt
6. Analyse & oppsummering
7. Kolonneforklaringer

Kolonnenes rekkefølge og standardetiketter er deklarert i
`src/auto_analyse/report.py`: CATEGORY_HEADERS, COMPETITOR_HEADERS og ACTION_HEADERS.
Butikkavhengige etiketter følger valgt navn, og prosentetiketter følger tersklene.
De tre produktlistene har samme 14 kolonner. Ingen grafer, Utvikling, Datakvalitet
eller separat Måltall-fane. Dashboard er aktivt ved åpning.

De åtte KPI-kortene er A5, D5, G5, J5, A9, D9, G9 og J9.
Tall lagres numerisk. Prosentkort viser hele prosent, andre prosentkolonner én desimal.
Valuta vises med konfigurert valutakode. Rapporten er et ferdig beregnet snapshot.

68 cellenotater: Kategorier!A1:M1, Konkurrenter!A1:G1, A1:N1 i de tre
produktlistene, Kolonneforklaringer!A1:C1 og dashboardets A45/D45/F45.
Synlige forklaringer og cellenotater skal ha samme tekst.

Kildetekst lagres som tekst, ikke som Excel-formler. Produktlenker blir hyperlenker
bare for HTTP(S). Notatforfatter og dokumentforfatter er Auto Analyse.

## Filer og bevaring

CLI-en skriver `.xlsx`, `.json` med KPI-er/kildehash/innstillinger og
`.notes.json` med `version: 1` og liste av sheet/cell/header/note.
Ikke-endelige KPI-verdier blir JSON-null. Prosenttekst uten grunnlag viser
«Ikke beregnbart». Syntetiske demoer har `demo: true`.

Alle outputbaner kontrolleres før første skriving. Eksisterende fil krever
`--overwrite`. Input kan ikke erstattes av rapport eller sidefil, heller ikke
via hardlink eller med overwrite. Endret råfil under innlesing avvises.
Vanlige skrivefeil kan etterlate delvis output; korriger årsaken og kjør på nytt
med en ny bane eller bevisst overwrite.

## Syntetisk akseptansegrunnlag

`examples/demo/retail.csv` genereres av `scripts/generate_demo_data.py`.
Demoen har 32 rader, 8 produkter og 2 dager. KPI-kort: 8, 87,5 %, 5, 40 %, 2,
2, 4 %, 1. Marginvakt: 1. Detaljert regnegrunnlag står i
[dataformatene](../../../../docs/data-formats.md).

`tests/test_example_report.py` og `tests/test_cli_safety.py` kontrollerer
beregninger, arbeidsbok, konfigurasjon og filvern. Ingen reelle crawl-uttrekk
eller historiske kunderapporter kreves for testing.
