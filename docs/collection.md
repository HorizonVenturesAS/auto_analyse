# Fra Prisradar til rapport

Auto Analyse er rapportdelen. Produktoppdagelse og nettinnsamling utføres i det
separate prosjektet `prisjakt-catalogue`, med Prisradar.no som datakilde.
Navnet «prisjakt» i mappen endrer ikke datakilden.

## Før du begynner

Du trenger tilgang til innsamlerprosjektet fra eieren. Det følger ikke med dette
repoet, og det er ikke publisert en verifisert kloneadresse her.
Plasser det gjerne ved siden av `auto_analyse`, eller oppgi faktisk plassering til agenten.

Bruk en lokal agentøkt med tilgang til begge mappene. Les innsamlerens AGENTS.md,
README.md og aktuell `python -m prisradar.api_collector --help`.
Den personlige skillen `prisradar-analyse` kan brukes hvis den finnes, men dette
prosjektet forutsetter ikke at den er installert hos en ny bruker.

For **brandanalyse** trenger du leverandør/eierkontekst, merkeliste og eventuelle
kategoriavgrensninger. Innsamleren finner produsent-ID-er, traverserer produktlister,
henter butikktilbud og følger eksplisitte varianter. Kontroller tvetydige merker og
variantidentitet før du kaller et produkt bekreftet. Listen på Prisradar er ikke
automatisk hele produsentens faktiske katalog.

For **retailanalyse** trenger du også målbutikkens eget sortiment, priser og en
felles produktkobling til konkurrenttilbudene. Adapterstøtten må kontrolleres i
innsamlerprosjektet. Et nytt butikkdomene i en TOML-fil lager ingen ny innsamleradapter.
Brandeksport kan ikke bare døpes om og brukes som retailgrunnlag.

## Eksempel på isolert brandinnsamling

Kommandoene under beskriver CLI-en kontrollert 1. november 2026. Kontroller hjelp
og prosjektinstruksjoner på den versjonen du faktisk har. De kjøres **i innsamlerprosjektet**,
med dets Python-miljø. En egen mappe per analyse hindrer sammenblanding.

1. Lag `data/min-analyse/merker.xlsx` med overskrifter i første rad,
   leverandørdomene i kolonne A og merke i kolonne B. Bruk reelle bestilte merker,
   ikke dette repoets oppdiktede demoer.
2. Lag `data/min-analyse/brand_context.json` som et JSON-objekt med merket som nøkkel
   og dokumenterte aliaser/kildeopplysninger som verdi. Kontroller gjeldende format
   i innsamleren. Et tomt objekt `{}` inneholder ingen verifiseringsbevis.
3. Initialiser den nye analysen, og gjennomfør først en avgrenset pilot:

```sh
python -m prisradar.api_collector init --workbook data/min-analyse/merker.xlsx --brand-context data/min-analyse/brand_context.json --data-dir data/min-analyse --output-dir outputs/min-analyse
python -m prisradar.api_collector run --limit 20 --batch-size 25 --data-dir data/min-analyse --output-dir outputs/min-analyse
python -m prisradar.api_collector status --data-dir data/min-analyse --output-dir outputs/min-analyse
```

`--limit` teller jobber, ikke produkter. Kontroller pilotens identiteter, kategoriomfang,
varianter og tilbud. Fortsett deretter samme kø uten limit:

```sh
python -m prisradar.api_collector run --batch-size 25 --data-dir data/min-analyse --output-dir outputs/min-analyse
python -m prisradar.api_collector export --data-dir data/min-analyse --output-dir outputs/min-analyse
```

Ved gjenopptakelse: finn eksisterende database og kontroller prosess/status først.
Bruk samme datamappe. Ikke kjør init eller prepare bare fordi arbeidet ble avbrutt.
`prepare` starter en ny observasjonsrunde; `export` henter ikke nye priser.
En tom kø er ikke bevis på komplett katalog.

Standardtransporten i den kontrollerte innsamleren er lesende GraphQL mot
`https://gql.prisradar.no/`. Den kjører lokalt og krever våken maskin/nett.
Behold innsamlerens hastighetsgrense og én arbeider per datamappe. Ved
401/403/429 eller tilgangsutfordring: bevar fremdrift og rapporter hindret.

## Overføring til Auto Analyse

1. Kontroller innsamlerens status, `brand_coverage.csv`, unntak og eventuelle
   ufullstendige tilbud. Bevar kontrollgrunnlaget lokalt i innsamlerprosjektet.
2. Bruk `catalogue.csv` fra den valgte analysen, ikke `discovered_urls.csv`.
   Kopier filen urørt til `auto_analyse/data/inbox/brands/catalogue.csv`.
3. Kontroller kolonnene mot [datakravene](data-formats.md). Bevar produkt-ID-er,
   observasjonstider, brukt-/ferskhetsflagg og kontrollårsaker. Ikke gjør
   ukjent status om til gyldige tilbud for å få flere rader i rapporten.
4. Kjør fra Auto Analyse:

```sh
python -m auto_analyse.brand data/inbox/brands/catalogue.csv --config config/brand.toml
```

Den kontrollerte brandeksporten har de obligatoriske feltene. Eldre eller tilpassede
eksporter må valideres. Ved formatforskjeller: dokumenter feltmapping og lag en
separat tilpasset fil, mens originalen beholdes. Ikke gjett manglende fakta.

Lever rapportlenker, innsamlingens tidsrom, antall produkter/tilbud, dekningsstatus
og uavklarte forhold. Pris og lager er observert hos Prisradar; direkte butikkbekreftelse
gjelder bare de tilbudene som faktisk er kontrollert hos butikken.

## Separat kontroll av kildepris og butikkvariant

En eksport fra API-et er råobservasjoner, ikke godkjente prissammenligninger.
Brandmotoren bruker `source` som standard: gyldige kildepriser kan sammenlignes
med variantkontroll og sperring av kjente beviskonflikter. Manglende direkte
butikkbekreftelse vises separat og sperrer ikke alene kildeprisen. Valgfri
`strict`-modus krever uavhengige butikkbevis før prisnøkkeltall beregnes.
Variantkontroll og priskontroll har uavhengige statuser.

Innsamlerens `prisradar.source_probe` kan kontrollere et avgrenset utvalg med
ferske API-kall og offentlige produktsider. `prisradar.verified_capture` lagrer
i tillegg direkte butikkbevis for eksplisitt oppgitte produkt- og tilbuds-ID-er.
Kontroller alltid aktuell `--help`. Bruk direkte produktadresser; klikksporing
og handlekurv er ikke kilder for denne kontrollen. Manglende butikkadresse,
tilgangshinder eller uklar pris/variant skal gi uavklart status.

Bevar originale HTTP-svar, forespørselsmetadata, tidsstempler og SHA-256 sammen
med et versjonert `evidence-manifest.json`. Kjør rapporten med
`--evidence-manifest <fil>`. Manifestets relative bevisbaner må ligge under
manifestmappen. Rapportmotoren validerer bindingene mot lagrede råbytes;
manuelt oppgitte godkjenningsflagg er ikke tilstrekkelig.

For uavhengig verifisering må alle tre observasjoner gjelde samme tilbud og sammenfallende produktvariant,
pris, valuta og prisgrunnlag innen fem minutter. Butikkens identitet må komme
fra butikkens eget produktbevis. API-produktets GTIN må aldri kopieres som
butikktilbudets GTIN. Mva, frakt og eventuelle medlemsvilkår kontrolleres separat.
Oppgitt kildecache-alder vises separat fra innhentingstiden og tillates bare
innen dokumentert cachepolicy og konfigurasjonens grense (standard åtte timer).
En hentet cacheside er ikke bevis på at butikkprisen ble oppdatert da.

### Avgrenset kilde- og butikkpilot

Disse modulene ligger i innsamlerprosjektet, ikke i denne Python-pakken.
Kontroller at den tilgjengelige innsamlerkopien har modulene med `--help`.
En klone eller push av Auto Analyse installerer eller publiserer ikke innsamleren.

- Produktfil: JSON-liste med `product_id` og kanonisk `url` per produkt,
  samt `gtin`/`model` bare når disse er dokumentert. ID-ene skal være tekst.
- Butikkfil: JSON-objekt med eksakt tilbuds-ID som nøkkel og direkte HTTPS-adresse
  til butikkproduktet som verdi. Manglende adresser skal ikke gjettes.
- Bruk en isolert datamappe for bevisfangst og én nettarbeider om gangen.

```sh
python -m prisradar.source_probe --products data/min-analyse/products.json --data-dir data/min-analyse/probe --output-dir outputs/min-analyse/probe
python -m prisradar.verified_capture --products data/min-analyse/products.json --data-dir data/min-analyse/verified --supplier leverandor.example --brand "Bestilt merke" --merchant-map data/min-analyse/merchant-map.json
```

Bytt eksempelnavnene med oppdragets faktiske kontekst. Bevisfangsten skriver
`captured-products.json`, `catalogue.csv`, `capture-status.json`, originale
HTTP-bevis og `evidence-manifest.json`. Fullført fangst betyr at observasjonene
er behandlet, ikke at alle tilbud er verifisert. Samme fangst kan gjenopptas med
samme input uten å fornye ferdige observasjoner; nye priser krever ny runde.
Ved innarbeiding i rapportinput skal et helt produktsnapshot brukes samlet.
Ikke erstatt bare et billigere enkelttilbud eller bland observasjonstidspunkter.

Start med kjente feiltilfeller og et reproduserbart tilfeldig utvalg. Avstem
utelatte tilbud og avvik før utvidelse. Kilderapporten viser eksplisitt kontrollomfang;
den skal ikke omtales som uavhengig butikkverifisert. Delvis strict-bekreftelse
gir en provisorisk rapport. Syntetisk beregning tillates bare eksplisitt i demo.
