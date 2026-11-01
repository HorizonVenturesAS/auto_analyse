# Auto Analyse i Claude Code

Bruk prosjektets felles instruksjoner:

@AGENTS.md

Les deretter README.md for oppsett og promptforslag. Dette repoet kjøres lokalt med
Python. Bruk terminaltilgang i Claude Code. Hvis en import ikke lastes automatisk,
les AGENTS.md direkte. Repo-skillen kan også leses som en vanlig Markdown-fil;
ingen personlig Codex-installasjon eller skill-mappe er nødvendig.

Velg retail eller brand ut fra oppdraget. Begge har en lokal syntetisk `--demo`.

For brand: les [brandkontrakten](docs/brand-report-contract.md). Standardmodusen
`source` sammenligner kildepriser med variant- og konfliktkontroll. Direkte
butikkbekreftelse rapporteres separat; `strict` er et valgfritt strengere utvalg.
Ikke velg strict eller demo som en automatisk løsning på manglende butikkbevis.

For nye brands/butikker: bruk ny oppdragskontekst og kontrollert kildeomfang,
ikke forrige analyses identitetsbeslutninger. Nye nettobservasjoner følger
[innsamlingsveiledningen](docs/collection.md) og innsamlerens egne instruksjoner.
