# Auto Analyse

Auto Analyse lager Excel-rapporter om priser og tilgjengelighet fra lokale råfiler.
Prosjektet er laget for å brukes sammen med en AI-agent i **Codex eller Claude Code**.
Du kan også kjøre alle rapportene direkte fra terminalen.

**Dette repoet henter ikke data fra nettet.** Innsamling fra Prisradar skjer i det separate
prosjektet `prisjakt-catalogue`. Her valideres og analyseres uttrekket, og rapporten bygges.
Se [innsamlingsveiledningen](docs/collection.md) når du vil hente nye data.

Alle data som følger med denne arbeidsversjonen er **syntetiske**. Produkter, GTIN-er,
leverandører, butikker og priser i demoene er oppdiktet. Adressene bruker `.example`.
Demoene trenger verken Prisradar, innlogging eller API-nøkkel.

## Velg riktig rapport

| Rapport | Når bruker du den? | Kommando |
|---|---|---|
| Retail | Én butikks priser og lager sammenlignes med konkurrentene | `python -m auto_analyse` |
| Brand | En leverandørs merker og produkter sammenlignes på tvers av butikker | `python -m auto_analyse.brand` |

Retail gir én rapport. Brand gir én rapport per leverandør i råfilen.
Rapportene er ferdig beregnede snapshots. Kjør programmet igjen ved nye data;
manuell redigering av Excel beregner ikke analysen på nytt.

Brandrapporter sammenligner som standard observerte kildepriser (`source`).
Variantkontroll og kjente pris-/kildekonflikter kan sperre tilbud. Bruk
`--evidence-manifest <fil>` for supplerende API-, offentlig side- og butikkbevis;
manglende butikkbevis vises som kontrollstatus og sperrer ikke alene kildeprisen.
Modusen `strict` krever uavhengig butikkbekreftelse. Se
[innsamlingsveiledningen](docs/collection.md) for fremgangsmåten.

## Start i Codex eller Claude

1. Klon eller last ned prosjektet og åpne **prosjektmappen** i en lokal kodeøkt.
2. I Codex: velg mappen som prosjekt. Agentinstruksjonene ligger i [AGENTS.md](AGENTS.md).
3. I Claude-appen: bruk **Claude Code med tilgang til den lokale mappen og terminalen**.
   [CLAUDE.md](CLAUDE.md) peker til de samme prosjektinstruksjonene.
4. Lim inn startprompten nedenfor. Agenten kan gjøre installasjonen og kjøre demoene.

En vanlig chat med bare opplastede filer gir ikke nødvendigvis tilgang til prosjektets
terminal. Velg en lokal kodeøkt. Rapportmotoren krever ingen modell-API-nøkkel;
tilgang til AI-appen ordnes separat.

Offisiell veiledning: [Codex-prosjektinstruksjoner](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[Claude Code på desktop](https://code.claude.com/docs/en/desktop) og
[CLAUDE.md](https://code.claude.com/docs/en/memory).

### Første gangs bruk

> Les AGENTS.md og README.md. Sett opp prosjektets virtuelle Python-miljø med de låste
> avhengighetene. Kjør begge syntetiske demoene, kontroller KPI-er, faner og kolonnenotater,
> og vis meg rapportene. Forklar forskjellen mellom retail og brand. Bruk kun demoene.

### Lag rapport fra egen råfil

> Les AGENTS.md og docs/data-formats.md. Lag brandrapport fra
> data/inbox/brands/catalogue.csv. Bruk config/brand.toml. Bevar råfilen, kontroller
> datagrunnlaget og oppgi rapportlenker, observasjonsperiode og viktige begrensninger.

For en butikkrapport kan du bruke:

> Lag retailrapport fra data/inbox/uttrekk.csv med konfigurasjonen
> data/min-butikk.toml. Kontroller at butikk, valuta og produktkoblinger er riktige.
> Skriv rapporten til outputs/min-butikk.xlsx og kontroller resultatet.

### Hent nye data og lag rapport

> Les AGENTS.md og docs/collection.md. Bruk det separate prisjakt-catalogue-prosjektet
> til å hente data fra Prisradar.no for leverandøren [domene] og merkene [merkeliste].
> Innsamlerprosjektet ligger i [mappe]. Bruk et eget analyseområde, kontroller
> merkeidentitet, varianter, tilbud, dekning og observasjonstid. Eksporter catalogue.csv,
> legg en urørt kopi i dette prosjektets data/inbox/brands/ og lag brandrapporten her.
> Oppgi uavklarte forhold. Ikke publiser data eller rapporter.

Erstatt feltene i hakeparenteser før du sender prompten. Innsamleren må være tilgjengelig
separat; den installeres ikke sammen med Auto Analyse.

### Fortsett i en ny økt

> Les AGENTS.md og eventuelle lokale notater i data/session.md. Kontroller faktiske
> filer og sist fullførte steg før du fortsetter. Fortsett med [oppgaven].
> Bruk eksisterende råfil med mindre jeg har bedt om nye observasjoner.

For å avslutte en arbeidsøkt med nyttig overlevering:

> Oppsummer valgt rapporttype, råfil, konfigurasjon, utførte kontroller, outputfiler og
> neste steg i data/session.md. Skill mellom fullført arbeid og uavklarte forhold.
> Ikke kopier rådata eller påstå at gamle priser er oppdatert.

## Installasjon fra terminal

Du trenger **Git og Python 3.11 eller nyere**. Excel er valgfritt for å åpne resultatet.
Python 3.12 er et godt utgangspunkt; CI kontrollerer 3.11 og 3.12.
Kommandoene under kjøres fra prosjektmappen.

Klon repoet og gå til prosjektmappen:

```sh
git clone https://github.com/HorizonVenturesAS/auto_analyse.git
cd auto_analyse
```

Repoet er privat; du må ha fått tilgang fra eieren. Ved publisering av endringer,
følg [delingskontrollen](docs/development.md#før-deling).

### Windows / PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e . -c constraints.txt
.\.venv\Scripts\python.exe -m auto_analyse --demo
.\.venv\Scripts\python.exe -m auto_analyse.brand --demo
```

Hvis du har Python 3.11, bruk `py -3.11` i første linje.
Miljøet trenger ikke aktiveres; kommandoene fungerer også når PowerShell blokkerer aktiveringsskript.

### macOS / Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/python -m auto_analyse --demo
.venv/bin/python -m auto_analyse.brand --demo
```

Resten av dokumentasjonen bruker `python` som kortnavn for Python i `.venv`.
Bruk den fulle plattformstien over, eller aktiver miljøet.

## Demoer og egne data

- Retaildemo: `examples/demo/retail.csv`, 32 observasjoner, 8 produkter og 2 dager.
- Branddemo: `examples/demo/brands.csv`, 11 observasjoner, 6 produkter og 2 leverandører.
- Retaildemoens rapport: `outputs/demo/retail.xlsx`.
- Branddemoens rapporter: `outputs/demo/brands/`.
- Demoene kan gjenskapes med `python scripts/generate_demo_data.py`.

Forventede KPI-er og forklaring på hver demosituasjon står i [dataformatene](docs/data-formats.md).
Demoer og rapporter er tydelig merket DEMO. Gjentakelse krever `--overwrite`, eller en ny målmappe.

Legg egne retailfiler direkte i `data/inbox/`, brandfiler i `data/inbox/brands/`.
Kopier en passende TOML-konfigurasjon til `data/` for private kundetilpasninger.

```sh
python -m auto_analyse data/inbox/uttrekk.csv --config data/min-butikk.toml -o outputs/min-butikk.xlsx
python -m auto_analyse.brand data/inbox/brands/catalogue.csv --config config/brand.toml
```

Støttet input: CSV, CSV.GZ, ZIP med én CSV og XLSX. Excel må ha én entydig rådatafane
med nødvendige kolonnenavn i første rad. `.xls` må først lagres som `.xlsx`.
CSV bruker komma som separator og punktum som desimaltegn.

Uten inputargument velger retail nyeste støttede fil i innboksen, uavhengig av demofilens dato.
Bare når innboksen er tom brukes den merkede retaildemoen. Brand velger bare fra sin egen
innboks og gir feilmelding hvis den er tom. `--demo` velger demo eksplisitt.

Eksisterende rapporter og sidefiler beskyttes mot overskriving. Bruk `--overwrite` når du
bevisst vil erstatte dem. Råfilen kan aldri være en outputfil, heller ikke med denne bryteren.
En eksplisitt `--config` som ikke finnes gir feil.

## Resultatet

### Prisgrunnlag i brandrapporter

`config/brand.toml` bruker `price_evidence_mode = "source"`. Gyldige kildepriser
og kildeoppgitt lager kan inngå etter variant-, ferskhets- og konfliktkontroll.
Direkte butikkbekreftelse vises separat. `strict` krever dokumentert API-,
offentlig side- og butikkpris, samt uavhengig lagerbevis for prissammenligninger.
Velg dette bare når oppdraget krever det; manglende bevis kan gi et tomt prisutvalg.
Begge moduser utelater feil/uavklarte salgsvarianter og kjente beviskonflikter.

Når et bevismanifest finnes, oppgi det også i source-modus:

```sh
python -m auto_analyse.brand data/inbox/brands/catalogue.csv --config config/brand.toml --evidence-manifest data/min-analyse/evidence-manifest.json --name-suffix _v2
```

Manifestet og bevisfilene må beholdes sammen, med relative bevisbaner under
manifestmappen. `--name-suffix` versjonerer Excel og alle sidefiler; det henter
ikke nye priser. For nye merker eller butikker følger agenten avgrensningen og
piloten i [innsamlingsveiledningen](docs/collection.md).

### Arbeidsbok og revisjonsspor

Retail har syv faner: Kategorier, Konkurrenter, Prisvarsler, Tilgjengelighetsrisiko,
Marginvakt, Analyse & oppsummering og Kolonneforklaringer.

Brand har åtte faner: Brands, Kategorier, Nettbutikker, Prisgap, Tilgjengelighet,
Kampanjer, Analyse & oppsummering og Kolonneforklaringer.

Ved siden av Excel ligger `.json` med KPI-er og `.notes.json` med kolonnenotater.
Brand skriver også `.observations.jsonl` med kontrollårsaker per observasjon.
Brandfanen Prisgap viser tilbudsvariantkontroll og separat omfang av prisbevis.
`audit_price_basis` skiller kildeobserverte og uavhengig bekreftede priser;
`audit_price_eligible` viser hvilke tilbud som faktisk brukes i prisgrunnlaget.
Alle disse filene kan inneholde kundedata og skal bli under `outputs/`.

Pris- og lagerdata beskriver det observerte utvalget. De dokumenterer ikke salg, margin,
markedsandel eller komplett sortiment. Brandrapporten bekrefter ikke brandeierskap.
Se [brandkontrakten](docs/brand-report-contract.md) og
[retailkontrakten](.agents/skills/retail-competitor-report/references/report-contract.md).

## Hvis noe feiler

| Melding / situasjon | Løsning |
|---|---|
| Python eller `auto_analyse` finnes ikke | Bruk Python fra `.venv`, og kjør installasjonen over. |
| Ingen brandråfil | Legg filen i riktig mappe, oppgi banen eller bruk `--demo`. |
| Manglende kolonner | Sammenlign med [datakravene](docs/data-formats.md). Ikke gjett koblinger eller flagg. |
| Ingen rader for målbutikk | Kontroller domene og scraper-nøkkel i konfigurasjonen. |
| Flere Excel-faner kvalifiserer | Lag en separat eksport med én rådatafane. Bevar originalen. |
| Konfigurasjonsfil finnes ikke | Kontroller filbane og at terminalen står i prosjektmappen. |
| Filen finnes allerede | Velg nytt outputnavn eller bruk `--overwrite`. |
| Permission denied / låst Excel-fil | Lukk rapporten i Excel og prøv igjen. |
| «Ikke beregnbart» | Les kontrollårsaker og datagrunnlag. Det betyr ikke null. |

For kodeendringer, tester og trygg deling: [utviklerveiledningen](docs/development.md).
