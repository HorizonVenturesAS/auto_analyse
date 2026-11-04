---
name: brand-competitor-report
description: Lag eller kontroller en brand-/leverandørrapport fra lokale tilbudsdata, med kontrollkø og målrettet variantverifisering før levering. Bruk retail-skillen for én målbutikk.
---

# Brandrapport

Bruk `python -m auto_analyse.brand` fra prosjektroten med prosjektets `.venv`.
Les AGENTS.md, docs/data-formats.md og relevante deler av docs/brand-report-contract.md.
Bruk bestilt råfil; ellers nyeste støttede fil direkte i data/inbox/brands/.
Bevar råfilen og skriv private tilpasninger under data/, rapporter under outputs/.
Merke-/leverandørkontekst og kategoriavgrensning må bekreftes for hvert nytt oppdrag.

Følg [verifiseringsflyten](../../../docs/verification-workflow.md): etter innhenting
kjøres automatisk kontroll over hele utvalget og en målrettet agentkontroll med
risikotilfeller og tilfeldig bredde. `python -m auto_analyse.verification` lager
en intern kontrollplan; den godkjenner ingen tilbud. Fordel uavhengige utvalg på
subagenter ved nye brands og vesentlige avvik, fortrinnsvis Luna Extra High når
tilgjengelig. Kontroller både feilaktige godkjenninger og for strenge avvisninger.

Kontroller eksakt salgsvariant per butikktilbud, ikke bare kildeproduktets navn
eller GTIN. Dokumenter egne butikkidentifikatorer, modell, pakning og relevante
mål. Skill ny identitetskontroll fra gamle pris-/lagerobservasjoner. Råverdier,
konflikter og observasjonstider må bevares i separat revisjonsspor.

`source` er standard. Manglende direkte butikkbevis er separat kontrollstatus,
ikke alene grunn til å tømme kildeprisanalysen. Ukjent variant er ikke godkjent.
Ikke lemp kontroller eller vis uavklarte priser som kvalifiserte for å få mer
utfylte rapporter. En særskilt indikativ visning krever uttrykkelig bestilling
og faktisk støtte i aktuell CLI. Kontroller alltid `--help` før valg av flagg.

Kjør rapporten på nytt fra dokumentert input etter kontrollrunden. Avstem
manifest, arbeidsbok, nevnere, tilbudseksklusjoner og kolonnenotater; behold
kontraktsfanene. Oppgi ordinært sammenlignbart utvalg separat fra eventuelle
indikative priser, faktisk kontrollomfang, periode og gjenværende begrensninger.
Ved ren omformatering av et kontrollert snapshot gjenbrukes dokumenterte
kontroller; ikke start ny innsamling. Før Git-deling gjelder docs/development.md.
