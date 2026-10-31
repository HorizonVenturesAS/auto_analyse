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

Kommandoene under beskriver CLI-en kontrollert 31. oktober 2026. Kontroller hjelp
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
