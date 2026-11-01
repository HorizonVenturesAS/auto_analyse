# Auto Analyse – prosjektinstruksjoner for AI-agenter

Dette er den delte arbeidsinstruksen for Codex og Claude Code.
Les README.md ved første økt. Ikke anta at tidligere chatter, personlige skills,
andre prosjekter eller en bestemt brukerkatalog finnes på denne maskinen.

## Velg arbeidsflyt

- **Demo / bli kjent:** kjør begge modulene med `--demo`. Demoene er helt syntetiske.
- **Retail / én butikk:** bruk `python -m auto_analyse` og repo-skillen
  [.agents/skills/retail-competitor-report/SKILL.md](.agents/skills/retail-competitor-report/SKILL.md).
  Hvis appen ikke oppdager skillen automatisk, les filen direkte.
- **Brand / leverandør / merkehus:** bruk `python -m auto_analyse.brand`.
  Les [dataformatene](docs/data-formats.md) og relevante deler av
  [brandkontrakten](docs/brand-report-contract.md). Retailregler om egen butikk gjelder ikke her.
- **Nye Prisradar-data:** les [innsamlingsveiledningen](docs/collection.md).
  Innsamling ligger i et separat prosjekt som brukeren må ha tilgang til.
  Les det prosjektets egne instruksjoner og aktuell CLI før oppstart.
  Ikke start innsamling for en oppgave som bare gjelder rapportering.
- Spør om perspektiv eller kilde bare hvis oppdraget ikke avklarer dette.
  Gjør rutinevalg innenfor bestillingen uten ekstra bekreftelser.

## Før kjøring

1. Arbeid fra prosjektroten. Kontroller `git status --short` før kodeendringer.
2. Bruk prosjektets `.venv`. Installer ved behov med
   `python -m pip install -e . -c constraints.txt`.
   Windows bruker `.venv/Scripts/python.exe`; macOS/Linux bruker `.venv/bin/python`.
3. Bruk oppgitt råfil. Uten fil: nyeste støttede fil direkte i
   `data/inbox/` for retail eller `data/inbox/brands/` for brand.
   Retaildemo er fallback bare ved tom innboks og må omtales som DEMO.
4. Kontroller skjema, analysemodus, målbutikk/leverandør, valuta og tidsperiode.
   Ikke fyll inn ukjente identiteter, tilbudsflagg eller lagerstatus ved gjetting.

## Data og output

- Bevar råfiler. Lag eventuell formattilpasning som separat fil under `data/`,
  med dokumentert mapping og observasjonstider.
- Bruk de versjonerte CLI-ene. Ikke gjenskap rapportberegningene i en ad hoc-notatbok.
- Output skal ligge i `outputs/`. Ikke skriv rapporter over input, kode eller demo-CSV-ene.
- Eksisterende rapporter krever ny filbane eller bevisst `--overwrite`.
- Standard retailkonfigurasjon er historisk Flisekompaniet. Bruk riktig TOML for andre butikker;
  navn, valuta, lagerstatus og terskler styrer rapporttekstene.
- Ekte rådata, rapporter, kilde-URL-er fra oppdrag, session-notater og tilpasset
  kundekonfigurasjon skal ligge under ignorerte `data/` eller `outputs/`.
- Bare generatorens syntetiske CSV-filer skal versjoneres som eksempler.
  Ikke bruk `git add -f` på datafiler. Ikke commit/push eller omskriv historikk uten bestilling.

## Brand: prisgrunnlag, identitet og nye analyser

- Standard er `price_evidence_mode = "source"`: sammenlign observerte kildepriser
  og kildeoppgitt lager. Manglende direkte butikkbekreftelse er en separat
  kontrollstatus, ikke alene en grunn til å tømme prisanalysen.
- Velg `strict` bare når oppdraget krever uavhengig butikkbekreftelse av pris og
  lager. Forklar konsekvensen for sammenligningsgrunnlaget. `synthetic` er kun
  for eksplisitt demo/test, aldri en snarvei for ekte data.
- Behold tilbudsvis variantkontroll og kjente beviskonflikter i begge moduser.
  Feil eller uavklart salgsvariant, manuelle kontrollflagg og ugyldige bevis
  skal ikke omgås for å få flere priser. Lik GTIN overstyrer ikke et konkret avvik.
- Bruk `--evidence-manifest` når kilde-/butikkbevis finnes. Bevar originalbytes,
  ID-er, hash og observasjonstider; rapportgenerering fornyer ikke bevisene.
  Skill kildesamsvar, butikkpris, variant og lager i leveransen.
- For nye brands eller butikker: avklar oppdragets merke-/leverandørkontekst,
  aliaser og kategoriomfang på nytt. Gamle produsent-ID-er, butikkadaptere og
  kundekonfigurasjoner er ikke automatisk godkjenning for et nytt oppdrag.
  Legg analysespesifikke avvisninger og bevis under ignorerte `data/`.
- Ved ny innhenting: kontroller kjente risikotilfeller og et reproduserbart
  tilfeldig pilotutvalg før utvidelse. Kontroller faktisk adapter-/parserstøtte;
  ikke gjett manglende butikkidentitet eller kopier produkt-GTIN til tilbuds-GTIN.
- Les [brandkontrakten](docs/brand-report-contract.md) for statuser og nevnere.
  «Ikke beregnbart» brukes ved manglende kvalifiserende grunnlag, ikke som en
  generell erstatning for kildepriser uten direkte butikkbevis.

## Verifisering og kontrakt

- Etter endring i kode, konfigurasjon, layout eller demoer:
  `python -m unittest discover -s tests -v` og
  `python scripts/generate_demo_data.py --check`.
- Kontroller KPI-kort, fanerekkefølge, tabelloverskrifter, notater og fravær av
  Excel-feil. Ved layoutendringer: åpne eller render berørte demoark hvis verktøy finnes;
  oppgi hvis visuell kontroll ikke kunne utføres.
- Ved vanlig rapportkjøring: kontroller manifest og arbeidsbok; ikke endre beregningene.
- Behandle TOML, KPI-definisjoner, kolonner og fanelayout som offentlig kontrakt.
  Oppdater relevant rapportkontrakt og tester ved tilsiktede endringer.
- Ikke legg til grafer eller fanene Utvikling, Datakvalitet eller separat Måltall
  uten uttrykkelig bestilling. KPI-ene ligger i Analyse & oppsummering.
- Nye kjøreavhengigheter må være nødvendige for den portable CLI-en og deklareres i
  `pyproject.toml`. Oppdater `constraints.txt` og test ved versjonsendringer.
- Før deling: følg [utviklerveiledningen](docs/development.md), inkludert historikkontrollen.

## Overlevering og nye økter

Oppgi rapportlenker, inputperiode, viktigste KPI-er og konkrete databegrensninger.
Ikke påstå komplett markedsdekning, bekreftet brandeierskap, salgseffekt eller margin.
Ny rapportgenerering oppdaterer ikke kildeprisene.

Ved behov lag korte lokale notater i `data/session.md`: oppdrag, filbaner,
konfigurasjon, fullførte steg, kontroller, output og neste steg. På neste økt må agenten
kontrollere faktiske filer før notatene legges til grunn. Ikke skriv kundespesifikk
historikk i denne filen, README eller skillen.
