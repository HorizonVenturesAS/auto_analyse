# Auto Analyse

Dette repoet lager den faste pris- og tilgjengelighetsrapporten for Flisekompaniet fra et nytt crawl-uttrekk. Beregninger, kolonner, terskler og Excel-layout er versjonert, slik at samme type rådata gir samme rapportstruktur uten en lang prompt.

## Kom raskt i gang

```powershell
git clone https://github.com/HorizonVenturesAS/auto_analyse.git
cd auto_analyse
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Legg den nye `.csv`, `.csv.gz`, `.zip` eller `.xlsx`-filen i `data/inbox/`, og kjør:

```powershell
auto-analyse
```

Programmet velger den nyeste råfilen og skriver rapporten og et JSON-sammendrag til `outputs/`. Du kan også oppgi fil og mål eksplisitt:

```powershell
auto-analyse data/inbox/nytt_uttrekk.csv -o outputs/innsiktsrapport.xlsx
```

På macOS/Linux brukes samme kommandoer, men miljøet aktiveres med `source .venv/bin/activate`.

## Bruk med Codex

Åpne repoet og skriv for eksempel:

> Analyser den nyeste råfilen og lag standardrapporten.

`AGENTS.md` og repo-skillen `$retail-competitor-report` forteller Codex hvilken kommando, rapportkontrakt og kontrollrutine som skal brukes. Du kan også starte eksplisitt med:

> Bruk $retail-competitor-report på filen i data/inbox.

## Hva rapporten inneholder

Rapporten har alltid disse fanene:

1. `Kategorier`
2. `Konkurrenter`
3. `Prisvarsler`
4. `Tilgjengelighetsrisiko`
5. `Marginvakt`
6. `Analyse & oppsummering`
7. `Kolonneforklaringer`

Det opprettes ingen grafer, og fanene `Utvikling`, `Datakvalitet` og en separat `Måltall`-fane inngår ikke. Måltallene ligger i `Analyse & oppsummering`.

## Definisjoner og konfigurasjon

Standardene ligger i `config/report.toml`. Der kan målaktør, scraper-nøkler, lagerstatus og terskler endres. Beregningskontrakten og obligatoriske råkolonner er dokumentert i `.agents/skills/retail-competitor-report/references/report-contract.md`.

Viktige standarder:

- Prisleder: egen pris er innenfor 1 % av billigste tilgjengelige konkurrent.
- Prisvarsel: egen pris er mer enn 5 % over billigste tilgjengelige konkurrent.
- Kritisk prisvarsel: egen pris er mer enn 15 % over billigste tilgjengelige konkurrent.
- Marginvakt: egen pris er mer enn 5 % under alle tilgjengelige konkurrenter.
- Pris sammenlignes bare når både Flisekompaniet og minst én konkurrent er `in_stock`.

## Eksempler og kvalitetssikring

- `examples/raw/` inneholder det komplette sju-dagersuttrekket komprimert som ZIP.
- `examples/reference/` inneholder den godkjente reviderte rapporten som visuell referanse.
- `python -m unittest discover -s tests -v` kjører en full ende-til-ende-kontroll mot kjente KPI-er og rapportstrukturen.
- GitHub Actions kjører samme kontroll på alle pushes og pull requests.

Rådata i `data/inbox/` og genererte rapporter i `outputs/` ignoreres av Git som standard. Dermed blir nye kundedata ikke lastet opp ved et uhell.
