# Utvikling, testing og deling

Start med [AGENTS.md](../AGENTS.md). Kjør fra prosjektroten med Python i `.venv`.

## Kontroller endringene

```sh
python -m pip install -e . -c constraints.txt
python -m unittest discover -s tests -v
python scripts/generate_demo_data.py --check
python scripts/check_share_ready.py --working-tree-only
```

Testene bruker bare syntetiske data og midlertidige mapper. De dekker beregninger,
produktidentitet, inputformater, råfilvern, overskriving, konfigurasjon, notater og
arbeidsbokstruktur. Ingen nettinnsamling inngår.

CI kjører på Windows og Ubuntu med Python 3.11 og 3.12. Den kontrollerer også
delbare filer og Git-historikk. `constraints.txt` låser kjente avhengigheter;
`pyproject.toml` angir tillatte intervaller. Oppdater låsing bevisst og test igjen.

Ved layoutendringer kjører du demoene og åpner/render berørte ark.
Kontroller kortverdier, tekstbryting, overskrifter, notater og at ingen Excel-feil vises.
Det er ikke nødvendig å beholde genererte arbeidsbøker i Git.

Endringer i beregninger, kolonner, terskler eller rapportlayout krever oppdatert
[retailkontrakt](../.agents/skills/retail-competitor-report/references/report-contract.md)
eller [brandkontrakt](brand-report-contract.md), samt relevante tester.

## Før deling

Reelle eksempeldata er fjernet fra Git-historikken, og demoene er erstattet med
syntetiske data. Bruk en ny klone hvis du har en kopi fra før oppryddingen
31. oktober 2026, slik at gammel historikk ikke kommer tilbake ved en senere push.

En vanlig commit som sletter en datafil fjerner ikke eldre versjoner.
Kontroller derfor både delingsutvalget og historikken før nye endringer pushes.

Kjør:

```sh
python scripts/check_share_ready.py
```

Kontrollen leser både kandidatfilene i arbeidsmappen og filbaner i historikken som
kan nås fra Git-referanser. Exitkode 1 betyr at det finnes noe å rydde.
`--working-tree-only` er kun en lokal utviklingskontroll, **ikke klarsignal til push**.
Kontrollen er en konservativ fil-/demokontroll, ikke en komplett hemmelighetsskanner.
Git-ignorerte filer inngår ikke i delingsutvalget; de må heller ikke legges til med `-f`.

Når reelle data finnes i gammel historikk, velg sammen med prosjekteieren enten:

- en ny, gjennomgått kildekopi med ny Git-historikk, uten gammel `.git`, data og output; eller
- en kontrollert rensing av eksisterende historikk og alle relevante referanser.

Ikke push gammel historikk i mellomtiden. Historikkomskriving, commits og publisering
skal være eksplisitt bestilt. CI er en ekstra kontroll etter push, ikke en garanti
for å hindre første opplasting. Kjør derfor kontrollen **før** push.

Gjennomgå filutvalget med `git status --short` og `git diff --stat`, og etter staging
med `git diff --cached --name-status`. Kontroller at bare kode, dokumentasjon,
konfigurasjonsmaler og generatorens to syntetiske CSV-filer følger med.
Staged demoer kontrolleres også mot generatoren.

## Lokale filer

| Mappe | Formål | I Git? |
|---|---|---|
| examples/demo/ | To deterministiske, syntetiske CSV-er | Ja |
| config/ | Generelle konfigurasjonsmaler | Ja |
| data/inbox/ | Private retailuttrekk | Bare .gitkeep |
| data/inbox/brands/ | Private branduttrekk | Bare .gitkeep |
| data/ | Privat konfigurasjon og session.md | Nei |
| outputs/ | Rapporter, sidefiler og lokale forhåndsvisninger | Bare .gitkeep |
| .venv/, build/, __pycache__/ | Miljø og byggeartefakter | Nei |

Demo-CSV-er genereres av `scripts/generate_demo_data.py`.
Ikke erstatt dem med en kundes CSV. Kontrollen sammenligner eksakte bytes med
generatorens output. Nye demofiler må være tilsvarende syntetiske og tas inn bevisst.

Ved opprydding må du skille vanlige filer fra symbolske lenker/junctions.
Ikke følg lenker til delte verktøybiblioteker når du sletter lokale rapportmapper.
