---
name: retail-competitor-report
description: Lag og kontroller prosjektets standard retailrapport fra lokale pris- og lagerdata, eller kjør den syntetiske butikkdemoen. Bruk for én målbutikk mot konkurrenter. Leverandør- og brandrapporter bruker auto_analyse.brand og docs/brand-report-contract.md.
---

# Retailrapport

Bruk den versjonerte CLI-en i dette repoet. Rapporten har syv faner og åtte KPI-kort.
Denne skillen ligger i repoet og kan leses direkte av Codex eller Claude Code.

## Arbeidsflyt

1. Les prosjektets AGENTS.md og velg riktig input:
   - Bruk oppgitt råfil.
   - Ellers: nyeste støttede fil direkte i `data/inbox/`.
   - Ved demo eller tom innboks: bruk den syntetiske `--demo` og merk leveransen DEMO.
   - Ikke bruk filer under `data/inbox/brands/` i denne modulen.
2. Bevar råfilen. Kontroller datakravene i
   [rapportkontrakten](references/report-contract.md) ved ukjent skjema.
   Produktkoblingen må finnes før import; rapporten gjør ikke produktoppdagelse.
3. Bruk prosjektets Python-miljø. Installer ved behov med
   `python -m pip install -e . -c constraints.txt` fra prosjektroten.
4. Kjør `python -m auto_analyse <input> --config <toml> -o outputs/<rapport>.xlsx`
   eller `python -m auto_analyse --demo`.
   `config/report.toml` gjelder Flisekompaniet; demoen bruker `config/demo-retail.toml`.
   Bruk eksplisitt konfigurasjon for andre butikker.
5. Velg ny output eller bruk `--overwrite` når erstatning er ønsket.
   CLI-en beskytter både råfil og eksisterende rapport/sidefiler.
6. Før kundelevering fra nytt butikkgrunnlag: følg
   [verifiseringsflyten](../../../docs/verification-workflow.md). Lag en lokal
   kontrollkø med `python -m auto_analyse.verification <input> --mode retail
   --config <toml> --output outputs/<analyse>/review-plan.json`. Kontroller hele
   målbutikkens utvalg, også varer uten prisvarsel, og fordel avgrensede risikosaker
   og tilfeldig bredde på subagenter, fortrinnsvis Luna Extra High når tilgjengelig.
   Bekreft målbutikk-SKU mot konkurrentens konkrete variant; GTIN/felles produkt-ID
   alene overstyrer ikke modell-, paknings- eller størrelsesavvik. Bevar gamle
   prisdatoer ved ny identitetskontroll. Dokumenter beslutninger separat, rett
   både feiltreff og for strenge avvisninger, og kjør rapporten på nytt.
   Uavklarte treff inngår ikke i kvalifisert indeks, rangering eller prisvarsler.
   Ved rene presentasjonsendringer gjenbrukes tidligere dokumenterte kontroller.
7. Kontroller JSON-manifest, de åtte KPI-kortene, fanerekkefølge og alle 68
   kolonne-/tabellnotater mot `.notes.json`. Notatene skal samsvare med synlige
   overskrifter, konfigurert butikknavn og terskler.
8. Ved kode-, konfigurasjons-, layout- eller demoendringer: kjør
   `python -m unittest discover -s tests -v` og demoenes `--check`.
   Ved vanlig rapportoppdatering holder kontroll av genererte artefakter.
9. Lever lenke til Excel, inputperiode og KPI-er. Beskriv databegrensninger.
   Ikke beregn salgseffekt eller margin fra eksterne prisobservasjoner alene.

## Rapportkontrakt og deling

Les [rapportkontrakten](references/report-contract.md) før beregninger eller layout endres.
Oppdater kontrakt og tester ved tilsiktede endringer. Behold syv faner og deres rekkefølge.
Ikke legg til grafer, Utvikling, Datakvalitet eller en separat Måltall-fane uten bestilling.

Kundedata og rapporter lagres under ignorerte `data/` og `outputs/`.
Bruk bare syntetiske demoer i versjonerte eksempler. Før publisering gjelder
[delingskontrollen](../../../docs/development.md).

## Google Sheets, bare når det er bestilt

Importer den ferdige arbeidsboken gjennom tilgjengelig Drive/Sheets-verktøy.
Repoet forutsetter ikke at en slik tilkobling finnes.

Bruk CLI-ens `.notes.json` etter konvertering. Dette er native cellenotater, ikke
trådkommentarer. Les faktisk arkmetadata og de oppgitte headercellene.
Kontroller arktittel og headertekst før du setter manglende/ulike `CellData.note`
med `updateCells` og kun `fields: "note"`. Ikke gjett nye celleposisjoner.
Les alle 68 notater tilbake, og kontroller et synlig notat i UI når mulig.
Bekreft destination og layout før Sheets-lenken leveres.
