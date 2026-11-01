# Brandinnsikt – rapportkontrakt v4

Denne kontrakten gjelder bare `auto_analyse.brand` og `auto-analyse-brand`.
Retailmodulen har eget skjema og egen syvfaners kontrakt. Velg modul etter perspektiv.

## Kjøring og isolasjon

```powershell
python -m auto_analyse.brand data/inbox/brands/catalogue.xlsx --config config/brand.toml
python -m auto_analyse.brand data/inbox/brands/catalogue.xlsx --supplier leverandor.example
```

Etter `python -m pip install -e .` er også `auto-analyse-brand` tilgjengelig.
Uten input leses kun nyeste støttede fil direkte i `data/inbox/brands/`.
Modulen bruker aldri retailer-innboksen eller retailer-eksempeldata som fallback.
Flisekompaniets eksisterende, ikke-rekursive filoppdagelse velger ikke denne undermappens filer.

Én arbeidsbok skrives per normalisert leverandørdomene. `supplier` er en oppgitt
tilknytning, ikke dokumentasjon på brandeierskap. Ulike URL-stier på samme
leverandørdomene samles; de opprinnelige verdiene finnes i manifestet.
Butikkdomener normaliseres med små bokstaver, uten `www.`, skjema, port og sti.
En markedsplass teller som ett butikkdomene, ikke som dens eventuelle underliggende selgere.

Standardmål er `outputs/brands/<kildefil>-<kildehash>-<konfigurasjonshash>/`.
Bruk `--output-dir` for en annen mappe. Leverandørnavn får trygg filslug og hash
for å unngå navnekollisjoner. Eksisterende resultater krever eksplisitt `--overwrite`.
Alle mål kontrolleres før første eksport. Råfilen overskrives aldri.

`--config` leser en eksplisitt TOML-fil og feiler ved manglende fil eller ugyldige verdier.
Uten argument brukes modulens innebygde standarder, identiske med `config/brand.toml`.
Endringer i TOML får derfor effekt når filen oppgis med `--config`.

## Input og produktidentitet

Støttet: XLSX, CSV, CSV.GZ og ZIP med én CSV. For XLSX kreves nøyaktig én
fane med obligatoriske kolonnenavn i første rad. Oppsummeringsfaner ignoreres.
Flere kvalifiserende faner eller manglende kolonner gir en eksplisitt feil.

Obligatorisk:

`supplier`, `requested_brand`, `product_id`, `title`, `brand`, `category`,
`retailer`, `offer_id`, `price`, `currency`, `availability`, `observed_at`,
`is_used`, `is_stale`.

Valgfritt: blant annet `gtin`, `size`, `color`, `regular_price`, `shipping`,
`offer_title`, `prisradar_url`, `retailer_url`, `price_qualifier`,
`review_reason`, `requires_id_lookup`. Manglende kolonner representeres som ukjent/tomt.
`club_price` og `bf_price` beholdes for sporbarhet, men brukes ikke som offentlig pris.
Pris og førpris forventes som numeriske verdier. Tomme, ikke-numeriske og
ikke-endelige priser er ikke sammenlignbare. Excel-feil eller uutfylte
formelcacher i input gir ikke gyldige priser.

Grain er leverandør + normalisert ønsket brand + Prisradar-produkt-ID.
Brandnormalisering ignorerer store/små bokstaver, tegnsetting og diakritikk.
Et produkt kan være en størrelse eller variant. Produktnavn brukes aldri som
join-nøkkel. GTIN beholdes som tekst, og ID-er auto-merges ikke på GTIN.
Ledende nuller bevares når de finnes i kilden; tapte nuller gjettes ikke.

Alle rader krever gyldig `observed_at` med eksplisitt UTC/offset. Siste eksakte
tidspunkt per produkt velges som ett snapshot; alle tilbud fra eldre tidspunkter
utelates. Input må derfor bruke samme produktsnapshot-tidspunkt for tilbud
som tilhører samme innsamling. Kildehistorikken beholdes i observasjonsfilen.
Eksakte duplikatrader tas bort fra beregning, men beholdes med audit-flagg.

### Tilbudsvarianter (v2)

En kildegruppering er ikke i seg selv bevis på lik salgsvariant. Den generelle
kontrollen i `auto_analyse.brand.variants` kjøres per tilbud før laveste
butikkpris velges. Resultatet er `compatible`, `conflict`, `unverified` eller
`not_applicable`. Sistnevnte betyr at ingen støttet variantakse ble funnet,
ikke at varen er uavhengig identitetsverifisert.

Kontrollen bruker modell og tilbudstittel, observerte attributter og valgfrie
tilbudsspesifikke identifikatorer. `product_attributes` og `offer_attributes`
kan inneholde JSON med navngitte kildeattributter. `offer_model`, `offer_gtin`
og `offer_review_reason` er valgfrie. Produktets GTIN må aldri kopieres til
tilbudets GTIN uten tilbudsspesifikt kildebevis. ID-er og modellkoder beholdes
som tekst; kompatibilitetsreferanser er ikke varenummer for selve salgsvaren.

Mål sammenlignes på samme akse, med desimalverdien og rollen bevart. En
diameter er ikke en lengde, og nominell spenning er ikke automatisk lik en
markedsført maksspenning. Manglende nødvendig variantbevis gir `unverified`.
Eksplisitte konflikter overstyrer også lik GTIN eller modell. En lik generell
produktfamilie eller et lignende modellstammenavn godkjenner ikke et annet sett.

`conflict`, `unverified` og `offer_review_reason` utelater det enkelte tilbudet
fra prisminima, prisgap, butikkposisjon, billigstandel og kampanjer. Andre
avklarte tilbud på samme produkt og fra samme butikk kan fortsatt brukes.
Råtilbudet slettes ikke. Sortiment- og lagertall beholder sitt eksisterende
grunnlag i observerte tilbud, slik kolonnenotatene forklarer.

Observasjonsfilen får `audit_offer_variant_status`,
`audit_offer_variant_reasons` og `audit_offer_variant_evidence`. Prisgap får
kolonnen **Tilbudsvariantkontroll**. Produktets eksisterende **Kontrollgrunn**
gjelder fortsatt flagg som sperrer hele produktet. Manifestet teller separat
tilbud med konflikt/uavklart variant og produkter med tilbudseksklusjoner.
Ingen nye faner innføres. Ikke-støttede akser, manglende kildeattributter og
ukjente produkt-/tilbudsidentiteter må fortsatt dokumenteres og ved behov
kontrolleres mot produsent-/butikksider; fravær av flagg er ingen fullgaranti.

CLI-argumentet `--name-suffix _v2` gir arbeidsbok og alle sidefiler samme
suffiks uten å overskrive en tidligere rapport.

## Prisgrunnlag og kontrollflagg

Et kvalifiserende pristilbud har identifiserbar butikk og tilbuds-ID,
endelig pris >0, konfigurert valuta, konfigurert lagerstatus, `is_used=false`,
`is_stale=false`, tom `price_qualifier` og ingen tilbudsvis variantutestengelse. Ugyldig eller ukjent boolsk verdi
kvalifiserer ikke. Laveste kvalifiserende tilbud per produkt/butikk velges;
tilbuds-ID og kilderad gir stabil rekkefølge ved lik pris.

Hele produktets priser holdes utenfor hoved-KPI-er ved:

- konflikt mellom ønsket brand og kildebrand, etter konfigurerte aliaser;
- motstridende metadata innen valgt produktsnapshot;
- samme GTIN på flere produkt-ID-er hos leverandøren;
- eksplisitt størrelseskonflikt mellom produkttittel/størrelse og tilbudstittel;
- kildefeltet `review_reason` eller `requires_id_lookup=true`;
- flere forskjellige rader med samme tilbuds-ID i produktsnapshotet;
- snapshot eldre enn konfigurert antall timer relativt til uttrekkets referansetid;
- høyeste/laveste kandidatpris større enn `extreme_price_ratio`.

Referansetiden er seneste gyldige observasjon i hele inputfilen og er den samme
også ved `--supplier`-filter. Den lagres i manifestet. Det er en relativ
snapshot-kontroll, ikke en påstand om ferskhet på dagen rapporten kjøres.

Den eldre produktvise størrelseskontrollen beholdes for eksplisitte
størrelse-/EU-uttrykk, med størrelsesending i produkttittel for
sko/støvler/sandaler/hansker. Tilbudsvariantkontrollen ovenfor supplerer denne
med støttede modeller og mål-/pakningsakser. Den gjør ikke generell fuzzy
matching, og konverterer bare enheter på sammenlignbare akser.
Prisratio 5 er en konfigurerbar kontrollregel, ikke et anbefalt prisgap eller
et bevis på kildefeil. Kontrollerte kandidatpriser vises i Prisgap, men gapene
vises som «Ikke beregnbart» og inngår ikke i aggregatene.

Ugyldige tilbud utelates enkeltvis. Produkter med gjenværende kvalifiserende
tilbud kan fortsatt sammenlignes hvis de ikke har produktkontrollflagg.
Årsakene finnes i `audit_price_exclusion` i observasjonsfilen.

## Definisjoner

- **Produkter:** unike produktnøkler i siste produktsnapshot.
- **Butikker:** observerte normaliserte domener med tilbuds-ID.
- **Med aktive tilbud:** minst ett identifiserbart butikktilbud, uavhengig av lager/priskvalitet.
- **Lagerandel:** produkter med minst én butikk på lager / observerte produkter i gruppen.
- **Prissammenlignbare:** minst to butikker med kvalifiserende pristilbud, uten produktkontrollflagg.
- **Prisgap valuta:** høyeste minus laveste kvalifiserende butikkpris.
- **Prisgap prosent:** høyeste/laveste kvalifiserende butikkpris minus 1.
- **Median prisgap:** median av produktgapene, lik produktvekt. Ingen omsetningsvekting.
- **Kun én butikk på lager:** akkurat én observert lagerførende butikk.
- **Uten tilbud på lager:** ingen observerte lagerførende butikker, også når det ikke finnes tilbud.

Prisanalysen er eksklusive frakt. Samme valuta kreves; ingen valutakonvertering.
Et produkt med én butikk har et observerbart prisnivå, men intet prisgap.
Tomt grunnlag gir `null` i JSON og «Ikke beregnbart» i Excel, aldri null prosent.
Metadata og lagertall beholdes også for produkter som er ekskludert fra prisanalysen.
Det finnes ingen målpris eller egen retailer-pris.

### Nettbutikker

Én rad per brand + butikk. Sortiment = observerte produkter hos butikken / alle
observerte produkter for brandet. Lagerandel bruker butikkens egne observerte
produkter som nevner. Manglende oppføring er ikke det samme som utsolgt.

Prisposisjon = median over produkter av butikkpris / medianpris hos øvrige
butikker minus 1. Krever minst `min_peer_stores` øvrige kvalifiserende butikker
(standard to). Butikken ekskluderes fra egen referanse. Grunnlag vises eksplisitt.
Butikker med ulik produktmiks har ulike sammenligningsgrunnlag; dette er ikke
en rangering på en felles varekurv.

Andel billigst har egen nevner: kvalifiserende produkter hvor minst én annen
butikk har kvalifiserende tilbud. Toleranse er 1 % som standard. Alle delte
førsteplasser teller; andelene på tvers av butikker kan summere til over 100 %.

### Tilgjengelighet og kampanjer

Tilgjengelighet har både produktrader (ingen tilbud, ingen på lager, én på lager)
og butikkspesifikke gap (butikk ikke på lager, andre på lager). Samme produkt
kan derfor finnes flere ganger; radantall er ikke et produkt-KPI.
`backorder`, `preorder` og `out_of_stock` beholdes som forskjellige statuser.

Kampanjer velger laveste gyldige offentlige pris per produkt/butikk uavhengig av
lagerstatus, og beregner rabatt bare ved endelig førpris > pris >0. Manglende
førpris på det billigste tilbudet erstattes ikke av førpris fra et dyrere tilbud.
Kontrollprodukter er synlige og merket i detaljlisten, men utelates fra
Nettbutikkers rabattantall. Rabatt = 1 - pris/førpris. Manglende førpris betyr
ukjent, og førpris dokumenterer ikke historisk salgspris.

## Arbeidsbok og sporbarhet

Fast rekkefølge:

1. Brands
2. Kategorier
3. Nettbutikker
4. Prisgap
5. Tilgjengelighet
6. Kampanjer
7. Analyse & oppsummering (aktiv ved åpning)
8. Kolonneforklaringer

Mørkeblå overskrifter, Carlito, blå/grå flater, åtte numeriske KPI-kort,
filtrering, frosne overskrifter og cellenotater følger det eksisterende
formspråket. Ingen diagrammer eller faner for Utvikling, Datakvalitet eller
separate Måltall. Presise kolonnenavn, rekkefølge, formater og notater er
deklarert samlet i `auto_analyse.brand.report.COLUMNS` og `SHEETS` og testes.
KPI-verdier er A6, D6, G6, J6, A10, D10, G10 og J10.

Rapporten er en ferdig beregnet snapshot-rapport fra den versjonerte Python-modulen.
Tall beregnes ikke på nytt ved manuell redigering av Excel-cellene. Kjør CLI-en
på nytt for oppdateringer. Kildetekst skrives som tekst, aldri som Excel-formler.
Kun HTTP(S)-lenker fra URL-feltene får hyperlenker.

Hver leverandør får fire filer:

- `.xlsx`: rapporten;
- `.json`: KPI-er, kildefil, SHA-256, innstillinger og outputbaner;
- `.notes.json`: eksakte tabelloverskrifter med cellereferanser og notater;
- `.observations.jsonl`: normaliserte kilderader for kun denne leverandøren,
  med kilderadnummer, snapshot-/duplikatflagg og grunner til priseksklusjon.

`audit_selected_store_offer` identifiserer valgt laveste priskandidat per butikk.
`audit_price_eligible` krever i tillegg at produktet ikke har kontrollflagg;
et produkt trenger fortsatt minst to slike butikker for å bidra til prisgap.
Andre kvalifiserende tilbud fra samme butikk får en eksplisitt eksklusjonsgrunn.

Råfilen er urørt. Observasjonsfilen er et normalisert revisjonsspor, ikke en
byteidentisk kopi av rådata. Leverandørrapporter inneholder ikke andre
leverandørers observasjoner.

## Verifisering

### Kildepris og uavhengig prisbevis (kontrakt v4)

`price_evidence_mode = "source"` er standard for kildebasert prisanalyse.
Gyldige kildepriser og kildeoppgitt lager brukes med eksisterende variant-,
ferskhets-, varetilstands- og vilkårskontroller. Manglende direkte butikkbevis
er en begrensning, ikke en priseksklusjon. Kjente kilde-/butikkpriskonflikter
eller ugyldige bevis sperrer det berørte tilbudet. Eksplisitt lagerkonflikt
sperrer tilbudet fra sammenligningen av varer på lager. Manglende bevis er aldri
det samme som verifisert. `audit_price_basis` skiller `source_observed` fra
`independently_verified`. Rapporten merkes PRISRADAR-PRISER – DELVIS KONTROLLERT.

`price_evidence_mode = "strict"` er et valgfritt strengere utvalg som også
krever direkte butikkbekreftelse av pris og lager. `--evidence-manifest` kobler
tilbudet til lagrede API-, offentlig side- og direkte butikkobservasjoner.
Motoren verifiserer SHA-256, relative filbaner, originale HTTP-metadata og
feltbindinger mot råresponsen. Bevis må gjelde eksakt produkt-ID, tilbuds-ID,
butikk, snapshot, pris, valuta og variant; transporttid og cachealder valideres.
I strict-modus utelater manglende eller motstridende bevis tilbudet før butikkminimum,
peer-priser, prisgap og kampanjesammenstillinger. Råprisen beholdes.

Variantkompatibilitet bekrefter ikke pris. Kildesamsvar bekrefter ikke butikkens
pris eller lager. Revisjonssporet har derfor egne kilde-, butikkpris-, lager-,
cache-, mva- og prisgrunnlagsstatuser. For uavhengig prisverifisering kan ukjent
kilde-mva bare få bekreftet prisgrunnlag gjennom et eksakt prismatchet
butikktilbud med dokumentert mva inkludert; råstatusen for kilde-mva forblir
ukjent. Source-modus sammenligner kildeprisene uten å oppgradere mva-statusen.

`max_evidence_age_hours` er som standard 48 timer, og
`max_source_cache_age_hours` er åtte timer. Bevisenes transport-/observasjonstider
må ligge innen fem minutter av produktsnapshotet; bevisenes alder vurderes mot
kjøretidspunktet. Dette må ikke forveksles med den relative snapshotkontrollen
for selve råfilen. Original bevisdato og cachealder fornyes ikke ved eksport.

Analysearket viser publiseringsstatus og antall bekreftede/manglende bevis.
Prisgap har kolonnen `Prisbevis` etter `Tilbudsvariantkontroll`, med egne
tellere for kildesamsvar, butikkpris og bekreftet lager per produkt.
Priskolonnene heter `Laveste pris`, `Medianpris` og `Høyeste pris`; prisgrunnlaget
forklares i oppsummeringen og notatene. Delvis strict-kontroll merkes PROVISORISK.
Lager- og sortiment-KPI-er beskriver fortsatt
kildegrunnlaget og må ikke omtales som uavhengig butikkbekreftet.
Syntetisk unntak krever eksplisitt `--demo` eller testens `allow_synthetic=True`;
en konfigurasjonsfil eller et CSV-flagg kan ikke alene åpne prisporten.

Kjør `python -m unittest discover -s tests -v`. Brandtestene dekker prisgap,
én stemme per butikk, peer-median uten egen butikk, ulike nevnere, delt billigst,
snapshotvalg, kontrollflagg, manglende grunnlag, kampanjer, leverandørisolasjon,
skjemavalidering, råfilbevaring, overwrite-vern, faner, KPI-kort, notater og
formelinjeksjon. Retailtestene skal også bestå mot sitt syntetiske akseptansegrunnlag.

## Syntetisk demo og CLI-vern

`python -m auto_analyse.brand --demo` bruker `examples/demo/brands.csv` og
`config/demo-brand.toml`. Den gir to leverandørrapporter under `outputs/demo/brands/`,
med DEMO i tittelen og `demo: true` i manifestet. Demoen har 11 rader og 6 produkter.
Forventede tall står i [dataformatene](data-formats.md). Ingen reelle uttrekk kreves.

`--demo` og inputargument kan ikke kombineres. Låsefiler med `~$` ignoreres.
Input kan ikke være rapport eller sidefil, heller ikke via en hardlink eller med
`--overwrite`. Alle leverandørers målbaner kontrolleres før første eksport.
