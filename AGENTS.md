# Auto Analyse – prosjektinstruksjoner

Dette repoet produserer en fast, reproduserbar Excel-rapport fra retail crawl-data.

## Standard arbeidsflyt

- Når brukeren ber om å analysere nye Flisekompaniet-/Prisradar-data, bruk repo-skillen `$retail-competitor-report`.
- Behold råfilen urørt. Nye råfiler skal normalt ligge i `data/inbox/`.
- Bruk den versjonerte CLI-en (`python -m auto_analyse` eller `auto-analyse`) i stedet for å gjenskape beregningene i en ad hoc-notatbok.
- Hvis ingen fil er oppgitt, bruk den nyeste støttede filen i `data/inbox/`; bruk eksempelfilen bare når innboksen er tom eller brukeren ber om en test.
- Skriv genererte rapporter til `outputs/`. Ikke overskriv filen i `examples/reference/`.

## Endringer i analysekontrakten

- Behandle `config/report.toml`, kolonnene, KPI-definisjonene og fanelayouten som en offentlig kontrakt.
- Ved tilsiktede endringer skal både `.agents/skills/retail-competitor-report/references/report-contract.md` og testene oppdateres.
- Ikke legg tilbake grafene eller fanene `Utvikling`, `Datakvalitet` eller en separat `Måltall`-fane uten en eksplisitt bestilling.

## Verifisering

- Kjør `python -m unittest discover -s tests -v` etter endringer i beregninger, formatering, konfigurasjon eller eksempeldata.
- Kontroller minst KPI-kortene, fanerekkefølgen, tabelloverskriftene og fravær av ødelagte referanser.
- Nye avhengigheter skal være nødvendige for den portable CLI-en og deklareres i `pyproject.toml`.
