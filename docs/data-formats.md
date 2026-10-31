# Rådata og syntetiske eksempler

Velg format etter perspektiv, ikke filnavn. Begge moduler støtter UTF-8 CSV med
komma som separator, CSV.GZ, ZIP med én CSV og XLSX. Pris er et tall, for eksempel
`129.50`. Identifikatorer er tekst, slik at ledende nuller beholdes.

I XLSX skal nøyaktig én fane ha alle obligatoriske kolonnenavn i første rad.
Oppsummeringsfaner kan stå foran rådatafanen. Formelceller må ha lagrede verdier;
ren eksport av råverdier er tryggest. Rapportene endrer aldri råfilen.

## Retail: én butikk mot konkurrenter

Obligatoriske kolonner:

```text
observed_at_utc,scrape_run_id,scraper_key,retailer_name,retailer_domain,product_id,gtin,product_brand,model,catalogue_category,price,currency,before_price,availability_status,retailer_product_reference
```

| Felt | Betydning |
|---|---|
| observed_at_utc | Observasjonstid, helst ISO 8601 med Z, som 2026-01-02T12:00:00Z |
| scrape_run_id / scraper_key | Identitet for kjøringen og hvilken kildeadapter som leverte raden |
| retailer_name / retailer_domain | Butikkens navn og domene |
| product_id | **Felles produktnøkkel på tvers av egen butikk og konkurrenter** |
| gtin | Tekstidentifikator fra kilden, brukes til sporbarhet |
| product_brand / model / catalogue_category | Merke, produktnavn og kategori |
| price / currency / before_price | Observert pris, valuta og eventuell førpris |
| availability_status | Kildestatus, normalt in_stock, out_of_stock, backorder eller preorder |
| retailer_product_reference | Sporbar produkt-URL |

Én rad er en butikkobservasjon for et produkt på et tidspunkt.
Rapporten kobler på `product_id` og dag. Den gjør **ikke** automatisk GTIN-søk eller
produktmatching. Butikkenes forskjellige interne SKU-er må derfor kobles til en
felles produktnøkkel i innsamlingen. GTIN-likhet alene bekrefter ikke lik variant/pakning.

Kopier `config/demo-retail.toml` til `data/min-butikk.toml` og sett eget navn,
domene, scraper-nøkler, valuta, lagerstatus og rapporttittel. Standardfilen
`config/report.toml` er for Flisekompaniet. Bland aldri valutaer uten forhåndskonvertering
og dokumentert grunnlag. Standard terskler er 1 % prisledertoleranse, 5 % varsel,
15 % kritisk varsel og -5 % marginvakt.

### Retaildemoen

[retail.csv](../examples/demo/retail.csv) inneholder 8 oppdiktede produkter,
2 konkurrenter, 2 dager og 32 rader. Siste dag:

| Produkt | Situasjon |
|---|---|
| 000001 | Egen pris 120, konkurrent 100: 20 % over |
| 000002 | Egen pris 104, konkurrent 100: 4 % over |
| 000003 | Egen pris 90, konkurrent 100: marginvakt og prisleder |
| 000004 | Egen butikk utsolgt, konkurrent på lager: tilgjengelighetsrisiko |
| 000005 | Konkurrent finnes, men er utsolgt |
| 000006 | Ingen konkurrentobservasjon |
| 000007 | Lik pris 100: delt prisleder |
| 000008 | Egen pris 150, konkurrenter 100 og 120: 50 % over billigste |

Forventede åtte KPI-kort: **8 produkter, 87,5 % matchgrad, 5 sammenlignbare,
40 % prislederandel, 2 varsler >5 %, 2 varsler >15 %, 4 % median prisgap og 1
tilgjengelighetsrisiko**. Marginvakt teller 1 produkt. Første dag har noen andre
priser/lagerstatuser, slik at historikkberegningene også testes.

## Brand: leverandørens merker hos butikkene

Obligatoriske kolonner:

```text
supplier,requested_brand,product_id,title,brand,category,retailer,offer_id,price,currency,availability,observed_at,is_used,is_stale
```

| Felt | Betydning |
|---|---|
| supplier / requested_brand | Oppgitt leverandørdomene og merket som ble bestilt |
| product_id / title / brand / category | Prisradars produkt-ID og produktmetadata |
| retailer / offer_id | Butikkdomene og tilbudets identitet |
| price / currency / availability | Butikkpris, valuta og lagerstatus |
| observed_at | Kildens tidspunkt med eksplisitt tidssone |
| is_used / is_stale | Bruktstatus og gammel observasjon, true/false eller 1/0 |

Én rad er ett produkt × ett butikktilbud. Et produkt uten tilbud kan ha tomme
butikk-/tilbudsfelt. GTIN, size, color, regular_price, shipping, offer_title,
prisradar_url, retailer_url og review_reason er nyttige valgfrie felt.

Tilbud fra samme produktsnapshot skal ha samme observasjonstid. Seneste snapshot
velges per produkt. Ukjente brukt-/ferskhetsflagg skal ikke gjettes til false.
Manglende frakt er ukjent, ikke null. Leverandørtilknytning er ikke bevis for eierskap.

### Branddemoen

[brands.csv](../examples/demo/brands.csv) har 11 rader, 6 produkter og 2 leverandører:

- `demo-maker.example`: 4 produkter, 3 med tilbud, 3 butikker, 1 prissammenlignbart
  produkt, 75 % lagerandel og 40 % median prisgap. To produkter har bare én butikk
  på lager, ett har ingen tilbud. Ett tilbud viser en kampanje.
- `demo-tools.example`: 2 produkter. Ett har priser 200 og 220, altså 10 % gap.
  Det andre har 10 og 100 og flagges for ekstremt prisforhold, uten å inngå i pris-KPI-ene.

Datoene er faste for reproduksjon. De er ikke påstander om dagens marked.
Detaljerte regler finnes i [brandkontrakten](brand-report-contract.md) og
[retailkontrakten](../.agents/skills/retail-competitor-report/references/report-contract.md).
