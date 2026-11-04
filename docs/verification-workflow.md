# Innhenting, kontroll og målrettet verifisering

Standardflyten for nye brands og retailere er **avgrensning/pilot → innhenting →
automatisk kontroll → målrettet verifisering → rapport og sluttkontroll**.
Ved prisoppdateringer kjøres kontrollen igjen; agentarbeidet konsentreres om nye
produkter, endrede koblinger og avvik. En ren ny presentasjon av et frosset
uttrekk trenger ikke en ny innhentingsrunde eller full ekstern gjennomgang.

## 1. Avgrensning og pilot

Bekreft bestilt merke-/leverandør- eller butikkontekst, kategoriomfang, valuta,
produktnøkler og faktisk adapterstøtte. Bruk et isolert analyseområde.
Undersøk kjente risikotilfeller og et reproduserbart tilfeldig utvalg før full
innhenting. Et navnelikt produsentfacet er ikke dokumentert merkeidentitet.
Se [innsamling](collection.md); selve innsamleren er et separat prosjekt.

## 2. Innhenting og frosset grunnlag

Bevar råfiler, originalbytes, produkt-/tilbuds-ID-er, hash og observasjonstider.
Avstem listesider, kildeantall, varianter, tilbud, feil og reelle eksklusjoner.
Tom kø betyr ikke komplett katalog. Nye identitetsreferanser fra produsent eller
butikk fornyer ikke prisen eller lagerstatusen i et eldre snapshot.

## 3. Automatisk kontroll og kontrollkø

Bruk den versjonerte analysen før kundeeksport. Kontroller hele utvalget,
inkludert produkter uten tilbud og avviste koblinger. Lag en intern kontrollplan:

```sh
python -m auto_analyse.verification data/inbox/brands/catalogue.csv --mode brand --config config/brand.toml --sample-size 10 --seed 42 --output outputs/min-analyse/review-plan.json
python -m auto_analyse.verification data/inbox/retail.csv --mode retail --config data/min-butikk.toml --sample-size 10 --seed 42 --output outputs/min-butikk/review-plan.json
```

Brand støtter også `--evidence-manifest <fil>`. Syntetisk øving:

```sh
python -m auto_analyse.verification --mode brand --demo --output outputs/demo/brand-review.json
python -m auto_analyse.verification --mode retail --demo --output outputs/demo/retail-review.json
```

CLI-en kjører offline og bruker eksisterende rapportberegninger. Den skriver
bare den eksplisitte JSON-filen, beskytter råfil/konfigurasjon/bevismanifest og
krever `--overwrite` for eksisterende output. Planen inneholder alle analyserte
produktnøkler, kontrollflagg, kildeoppslag og en prioritert kø. Brands beholder
leverandør + merke + produkt-ID som nøkkel; retail beholder målbutikkens felles
produktnøkkel i rapportens seneste måldag, også uten prisvarsel. Planen er
`review_pending`, aldri et verifiseringsbevis eller godkjenningsflagg.

Samme input, konfigurasjon og seed gir samme tilfeldige utvalg uavhengig av
inputrekkefølge. `--sample-size` er ekstra kontrollbredde, ikke antall nettkall
eller et tak på risikokøen. `--gap-threshold` (standard 0,5 = 50 %) prioriterer
prisavvik; det endrer ingen beregnings-/akseptgrense. Planen må holdes under
ignorerte `outputs/` fordi den kan inneholde råtilbud og kundedata.

Automatikken finner bare signalene som finnes i skjemaet. Den bekrefter ikke
butikkkobling, navnealias, variant, eierskap eller komplett markedsdekning.
Retail-CSV-en kan mangle tilbuds-GTIN og variantbevis; disse må kontrolleres mot
innsamlerens grunnlag og faktiske butikksider. En felles produkt-ID er ikke
alene tilstrekkelig bevis for samme salgsvariant.

## 4. Målrettet agentkontroll

Prioriter konkrete konflikter, produkter med flere tilbud men manglende
sammenligning, store prisavvik, dyre varer, modellgenerasjoner, farge/størrelse,
pakning/inkluderte deler, delte GTIN-er og mulige dubletter. Kontroller også
for strenge avvisninger og noen tilsynelatende godkjente treff fra utvalget.
Mangel på to lagerførende butikker kan ikke løses ved å endre ukjent lager.

Fordel uavhengige produkt-/tilbudsutvalg på subagenter når verktøyene tillater
det; normalt opptil tre arbeidere til denne kontrollen. Foretrekk GPT-6 Luna
med Extra High (`xhigh`) for avgrenset kildesjekk når modellen er tilgjengelig.
Kontroller faktisk modell/innsats ved oppstart; oppgi hvis ønsket oppsett ikke
er tilgjengelig. Modellen er en arbeidsfordeling, ikke en godkjenningsregel.
Fastsett et avgrenset omfang for dypere nettkontroll etter volum og risiko.
En lokal gjennomgang av alle rader er ikke nettkontroll av alle tilbud.
Maskin-/verktøybegrensninger betyr ikke at kontrollen skal hoppes over; gjør
lokale kontroller og dokumenter gjenstående arbeid.

Gi hver agent eksakte produkt-/tilbuds-ID-er, fryste kilder og en egen
beslutningsfil. Én nettarbeider per innsamlingsområde og felles rategrense
gjelder fortsatt; parallell agentkontroll skal ikke multiplisere kildebelastning
eller gi samtidige database-/køskrivinger.

Beslutningene skal inneholde produktnøkkel, tilbuds-ID, vurdering
(`identity_supported`, `unverified` eller `conflict`), konkret grunn,
kildereferanse/observert faktum og kontrolltid. Skill kontroll av identitet,
pris, lager og kildeoverføring. `identity_supported` er et forslag som må
avstemmes mot faktisk tilbud og rapportreglene, ikke en generell godkjenning.
Ikke kopier produkt-GTIN til tilbud, bruk kompatibilitetskoder som eget varenummer
eller godta en hel modellfamilie. En ulik forkortelse er heller ikke alene bevis
på feil variant. Region, generasjon og konkrete målenes rolle må avklares.

Samle beslutningene i en separat, dokumentert tilpasningsfil under `data/`.
Bevar råverdier, gammel kontrollgrunn, kildereferanser og prisdato. Gjennomgå
agentenes dekning og tilbudsbindinger før nye felt tas inn. Bruk rapportmotoren
igjen; ingen ad hoc-beregninger eller manuelle godkjenningsflagg skal åpne priser.

## 5. Rapport og sluttkontroll

Skill **flere kvalifiserende tilbud etter avklaring** fra **flere viste,
uavklarte kildepriser**. Oppgi før/etter for ordinært sammenlignbart utvalg,
undersøkte produkter/tilbud, faktisk nettkontroll, løste/sperrede/uavklarte
tilfeller og eventuelle vesentlige endringer i minstepris eller butikkposisjon.
Antall utfylte celler eller færre kontrollflagg er ikke et kvalitetsmål alene.

Brand bruker fortsatt `source` som standard og beholder tilbudsvariantreglene.
En utvidet indikativ visning krever uttrykkelig bestilling og implementert CLI-
støtte i den aktuelle versjonen. Aldri bytt automatisk til slik visning fordi
agentkontrollen ikke ga nok priser. Kjente konflikter forblir sperret.
For retail skal uavklarte konkurrenttreff ikke inngå i kvalifisert prisindeks,
rangering eller prisvarsler; en særskilt kandidatvisning krever avtalt og faktisk
støttet presentasjon. Brandens flagg kan ikke brukes som retail-funksjonalitet.

Avstem manifest, arbeidsbok og revisjonsspor. Kontroller KPI-er, fanelayout,
kolonnenotater, tekstidentifikatorer og Excel-feil; render ved layoutendring.
Kundevisningen skal handle om priser, sortiment, butikker og tilgjengelighet,
med kort relevant kilde-/periode-/variantforklaring. Prosess, agentfiler og
bevisdetaljer beholdes internt. Ingen nye kontrollfaner eller grafer innføres.
