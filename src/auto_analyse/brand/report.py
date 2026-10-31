"""Brand workbook layout. No imports from or changes to the retail renderer."""
from __future__ import annotations

from pathlib import Path
import math
from urllib.parse import urlsplit

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from .analysis import BrandResult, NA
from .config import BrandConfig


INK, BLUE, LIGHT, GREY, GOLD = "0B1934", "264A96", "EAF2FF", "F8FAFC", "FFF7ED"
FONT = "Carlito"
# Each column owns its name, meaning, format and width; notes/glossary cannot drift.
# kind: text, count, pct, money, url
COLUMNS = {
    "brand": ("Brand", "Ønsket brand i kilden. Navnevarianter normaliseres; konfigurerte aliaser brukes til kontroll mot Prisradars brand.", "text", 22),
    "category": ("Produktkategori", "Produktkategori oppgitt i kilden.", "text", 35),
    "products": ("Produkter", "Antall unike produkt-ID-er fra Prisradar i siste snapshot per produkt, innen leverandør og brand. Varianter kan være egne produkter.", "count", 14),
    "stores": ("Nettbutikker", "Antall forskjellige observerte butikkdomener med identifiserbare tilbud. Markedsplasser teller som ett domene.", "count", 16),
    "with_offers": ("Med aktive tilbud", "Produkter med minst ett identifiserbart tilbud i siste snapshot, uavhengig av lagerstatus og priskvalitet.", "count", 19),
    "stock_rate": ("Lagerandel", "Andel produkter med minst ett tilbud merket på lager. På Nettbutikker er nevneren produktene observert hos butikken; ellers alle observerte produkter i gruppen. Pris- og matchingkontroll endrer ikke observert lagerstatus.", "pct", 16),
    "comparable": ("Prissammenlignbare", "Produkter uten kontrollflagg med gyldige, nye, ferske og ubetingede tilbud i rapportvaluta på lager hos minst to butikker.", "count", 21),
    "median_gap": ("Median prisgap", "Median av høyeste/laveste pris minus 1, beregnet per prissammenlignbart produkt. Hvert produkt vektes likt. Ikke beregnbart ved tomt grunnlag.", "pct", 19),
    "single_stock": ("Kun én butikk på lager", "Produkter med akkurat én observert butikk registrert på lager. Dette beskriver utvalget på Prisradar.", "count", 24),
    "no_stock": ("Uten tilbud på lager", "Produkter uten observerte tilbud på lager, inkludert produkter uten aktive tilbud. Andre lagerstatuser beholdes og regnes ikke som in_stock.", "count", 23),
    "review_products": ("Produkter til kontroll", "Produkter med pris-, variant-, brand-, GTIN-, kilde- eller ferskhetsflagg. Deres priser inngår ikke i pris-KPI-ene.", "count", 24),
    "retailer": ("Nettbutikk", "Normalisert domene fra tilbudet. Tom verdi i Tilgjengelighet betyr at raden gjelder produktet samlet.", "text", 25),
    "coverage": ("Observert sortimentsandel", "Produkter observert hos butikken delt på alle observerte produkter for brandet. Dette er ikke dekning av leverandørens komplette sortiment.", "pct", 27),
    "price_products": ("Grunnlag: billigst", "Antall produkter uten kontrollflagg der butikken og minst én annen butikk har kvalifiserende tilbud på lager.", "count", 21),
    "peer_products": ("Grunnlag: prisposisjon", "Antall produkter der butikken kan sammenlignes med minst konfigurert antall øvrige butikker (standard to). Kun kvalifiserende tilbud uten kontrollflagg.", "count", 24),
    "peer_gap": ("Avvik fra øvrig median", "Median av butikkpris/medianpris hos øvrige butikker minus 1, beregnet på de kvalifiserende produktene. Positiv verdi betyr høyere pris. Butikker kan ha ulikt produktgrunnlag.", "pct", 25),
    "leader_share": ("Andel billigst", "Andel av Grunnlag: billigst hvor butikkprisen er innenfor konfigurert toleranse av laveste pris (standard 1 %). Delt førsteplass teller for alle; andelene summerer ikke nødvendigvis til 100 %.", "pct", 18),
    "campaigns": ("Dokumenterte rabatter", "Produkt/butikk-par uten kontrollflagg der butikkens laveste kvalifiserende offentlige pris har oppgitt førpris over dagens pris, uavhengig av lagerstatus. Manglende førpris betyr ukjent.", "count", 24),
    "stock_gaps": ("Lagergap mot andre", "Produkter der denne butikken ikke er registrert på lager, mens minst én annen observert butikk er på lager.", "count", 23),
    "product_id": ("Produkt-ID", "Prisradars produkt-ID som tekst. Slås ikke automatisk sammen med andre ID-er selv om GTIN er lik.", "text", 17),
    "gtin": ("GTIN", "Kildens GTIN bevart som tekst. Ledende nuller som allerede er tapt i kildefilen kan ikke gjenopprettes sikkert.", "text", 20),
    "title": ("Produkt", "Produktnavn fra Prisradar.", "text", 54),
    "size": ("Størrelse", "Kildens størrelse; tom betyr ukjent. Eksplisitte størrelser i tilbudstitler kontrolleres også mot produktet.", "text", 15),
    "color": ("Farge", "Farge fra produktoppføringen. Fargelikhet mellom tilbud er ikke automatisk verifisert.", "text", 18),
    "offer_stores": ("Butikker med tilbud", "Ulike observerte butikker med identifiserbare tilbud for produktet, uavhengig av lagerstatus.", "count", 23),
    "stock_stores": ("Butikker på lager", "Ulike butikker med minst ett tilbud merket på lager. På butikkspesifikke lagerrader teller dette øvrige butikker.", "count", 21),
    "price_stores": ("Butikker med gyldig pris", "Butikker med positive, endelige priser i rapportvaluta for nye, ferske, ubetingede tilbud på lager. Laveste tilbud per butikk beholdes før produktets kontrollflagg vurderes.", "count", 25),
    "min_price": ("Laveste pris", "Laveste kvalifiserende butikkpris uten frakt. På kontrollrader er dette en kandidatpris som ikke inngår i pris-KPI-ene.", "money", 18),
    "median_price": ("Medianpris", "Median av laveste kvalifiserende pris per butikk, uten frakt. På kontrollrader vises kun kandidatpriser.", "money", 18),
    "max_price": ("Høyeste pris", "Høyeste av butikkenes laveste kvalifiserende priser, uten frakt. På kontrollrader vises kun kandidatpriser.", "money", 18),
    "gap_nok": ("Prisgap (valuta)", "Høyeste minus laveste butikkpris, bare for prissammenlignbare produkter. Valuta fremgår av tallformat og oppsummering.", "money", 21),
    "gap_pct": ("Prisgap (%)", "Høyeste butikkpris/laveste butikkpris minus 1. Tomt grunnlag eller kontrollflagg gir Ikke beregnbart, aldri null.", "pct", 17),
    "cheapest": ("Laveste hos", "Alle butikker med nøyaktig laveste kandidatpris. Listen er ikke en anbefaling eller dokumentasjon på autorisert forhandlerstatus.", "text", 42),
    "expensive": ("Høyeste hos", "Alle butikker med nøyaktig høyeste kandidatpris.", "text", 38),
    "status": ("Analysestatus", "Sammenlignbart, Ikke beregnbart eller Til kontroll. Bare Sammenlignbart inngår i prisgap-KPI-ene.", "text", 22),
    "review": ("Kontrollgrunn", "Konkrete flagg som holder produktets priser utenfor hoved-KPI-ene. Tomt betyr at automatiske kontroller ikke fant avvik; det er ingen garanti for riktig matching.", "text", 62),
    "observed_at": ("Observert (UTC)", "Tidspunkt for valgt snapshot av dette produktet. Siste tidspunkt per leverandør, brand og produkt-ID brukes; tilbud fra eldre snapshots blandes ikke inn.", "text", 29),
    "prisradar_url": ("Prisradar-URL", "Sporbar produktlenke fra kilden.", "url", 48),
    "issue": ("Tilgjengelighetsfunn", "Produktnivå: ingen tilbud, ingen lagerførende butikk eller kun én. Butikknivå: butikken mangler lager mens andre har varen. Flere rader kan gjelde samme produkt.", "text", 44),
    "availability": ("Lagerstatus", "Observerte lagerstatuser. backorder, preorder og out_of_stock skilles fra in_stock; dette er ikke fysisk lagertelling.", "text", 26),
    "offer_id": ("Tilbuds-ID", "Kildens tilbuds-ID for sporbarhet tilbake til observasjonsfilen.", "text", 18),
    "offer_title": ("Tilbudstittel", "Produktnavnet i det valgte butikktilbudet. Brukes ved kontroll av variant og pakning.", "text", 54),
    "price": ("Pris", "Laveste kvalifiserende offentlige pris per produkt/butikk, uten frakt. Kampanjer kan også omfatte tilbud som ikke er på lager.", "money", 18),
    "regular_price": ("Oppgitt førpris", "Førpris oppgitt av kilden for samme tilbud. Dokumenterer ikke historisk salgspris eller lovlig referansepris.", "money", 20),
    "discount": ("Oppgitt rabatt", "1 minus pris/oppgitt førpris. Beregnes bare når førprisen er endelig og større enn positiv salgspris.", "pct", 19),
    "retailer_url": ("Butikk-URL", "Direktelenke hvis den finnes i kilden; tomt felt betyr at den ikke er tilgjengelig.", "url", 48),
}
GROUP = ["products", "stores", "with_offers", "stock_rate", "comparable", "median_gap", "single_stock", "no_stock", "review_products"]
IDENTITY = ["brand", "product_id", "gtin", "title", "category", "size", "color"]
SHEETS = {
    "Brands": ("brands", ["brand"] + GROUP),
    "Kategorier": ("categories", ["brand", "category"] + GROUP),
    "Nettbutikker": ("retailers", ["brand", "retailer", "products", "coverage", "stock_rate", "price_products", "leader_share", "peer_products", "peer_gap", "campaigns", "stock_gaps"]),
    "Prisgap": ("products", IDENTITY + ["offer_stores", "stock_stores", "price_stores", "min_price", "median_price", "max_price", "gap_nok", "gap_pct", "cheapest", "expensive", "status", "review", "observed_at", "prisradar_url"]),
    "Tilgjengelighet": ("availability", IDENTITY + ["issue", "retailer", "availability", "stock_stores", "review", "observed_at", "prisradar_url"]),
    "Kampanjer": ("campaigns", IDENTITY + ["retailer", "offer_id", "offer_title", "price", "regular_price", "discount", "availability", "review", "observed_at", "prisradar_url", "retailer_url"]),
}
KPI_KEYS = ["products", "stores", "with_offers", "stock_rate", "comparable", "median_gap", "single_stock", "no_stock"]


def _put(ws, row, col, value, *, kind="text", config=None):
    cell = ws.cell(row, col)
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        value = NA if kind in {"count", "pct", "money"} else ""
    if hasattr(value, "item"):
        value = value.item()
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"  # Untrusted source text must never become an Excel formula.
    cell.font = Font(name=FONT, size=10, color=INK)
    cell.alignment = Alignment(vertical="top", wrap_text=False)
    cell.number_format = {"count": "#,##0", "pct": "0.0%", "money": f'#,##0.00 "{config.currency if config else "NOK"}"'}.get(kind, "General")
    if kind == "url" and isinstance(value, str) and urlsplit(value).scheme in {"http", "https"}:
        cell.hyperlink = value
        cell.font = Font(name=FONT, size=10, color="2563EB", underline="single")
    return cell


def _header(cell, note):
    cell.fill = PatternFill("solid", fgColor=INK)
    cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
    cell.alignment = Alignment(vertical="center", wrap_text=True)
    cell.comment = Comment(note, "Auto Analyse")
    cell.comment.width, cell.comment.height = 390, 120


def _table(wb, name, frame, keys, config, number):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B2" if name != "Kolonneforklaringer" else "A2"
    for col, key in enumerate(keys, 1):
        label, definition, _, width = COLUMNS[key]
        _header(_put(ws, 1, col, label), definition)
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[1].height = 42
    for row, values in enumerate(frame[keys].itertuples(index=False, name=None), 2):
        lines = 1
        for col, (key, value) in enumerate(zip(keys, values), 1):
            cell = _put(ws, row, col, value, kind=COLUMNS[key][2], config=config)
            if key in {"product_id", "gtin", "offer_id", "size"}:
                cell.number_format = "@"
            if key in {"title", "category", "offer_title", "review", "cheapest", "expensive", "issue"}:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                lines = max(lines, math.ceil(len(str(value or "")) / (COLUMNS[key][3] * .85)))
            if key in {"review", "status"} and value and value != "Sammenlignbart":
                cell.fill = PatternFill("solid", fgColor=GOLD)
        ws.row_dimensions[row].height = min(150, max(20, lines * 15 + 4))
    end = f"{get_column_letter(len(keys))}{max(1, len(frame) + 1)}"
    ws.auto_filter.ref = f"A1:{end}"
    if len(frame):
        table = Table(displayName=f"BrandTable{number}", ref=f"A1:{end}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        ws.add_table(table)
        for key in ("gap_pct", "median_gap"):
            if key in keys:
                letter = get_column_letter(keys.index(key) + 1)
                ws.conditional_formatting.add(f"{letter}2:{letter}{len(frame)+1}", ColorScaleRule(start_type="min", start_color=LIGHT, end_type="max", end_color="FBBF24"))
    else:
        _put(ws, 3, 1, "Ingen rader i denne kategorien.")
    ws.print_title_rows = "1:1"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    return ws


def _block(ws, start, end, text, fill=GREY, *, size=11, bold=False):
    ws.merge_cells(f"{start}:{end}")
    cell = ws[start]
    cell.value = text
    if isinstance(text, str):
        cell.data_type = "s"
    cell.font = Font(name=FONT, size=size, bold=bold, color="FFFFFF" if fill in {INK, BLUE} else INK)
    cell.fill = PatternFill("solid", fgColor=fill)
    cell.alignment = Alignment(vertical="center", wrap_text=True)
    return cell


def _dashboard(wb, result, config):
    s = result.summary
    ws = wb.create_sheet("Analyse & oppsummering")
    ws.sheet_view.showGridLines = False
    for col in range(1, 13):
        ws.column_dimensions[get_column_letter(col)].width = 14
    for row in range(1, 64):
        ws.row_dimensions[row].height = 22
    _block(ws, "A1", "L2", config.title, INK, size=19, bold=True)
    _block(ws, "A3", "L3", f"{s['supplier']}  |  {s['brands']} brands  |  {s['period_start'][:10]} – {s['period_end'][:10]} UTC  |  {config.currency}, uten frakt", LIGHT)
    for n, key in enumerate(KPI_KEYS):
        col, row = (n % 4) * 3 + 1, 5 + (n // 4) * 4
        start, end = get_column_letter(col), get_column_letter(col + 2)
        label, definition, kind, _ = COLUMNS[key]
        cell = _block(ws, f"{start}{row}", f"{end}{row}", label, BLUE, size=10, bold=True)
        cell.comment = Comment(definition, "Auto Analyse")
        value = s[key] if s[key] is not None else NA
        cell = _block(ws, f"{start}{row+1}", f"{end}{row+2}", value, LIGHT, size=24 if value != NA else 14, bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.number_format = "0.0%" if kind == "pct" else "#,##0"
    _block(ws, "A14", "L14", "Hva viser uttrekket?", BLUE, bold=True)
    count, review_count = f"{s['comparable']:,}".replace(",", " "), f"{s['review_products']:,}".replace(",", " ")
    _block(ws, "A15", "L16", f"{count} produkter kan prissammenlignes etter automatiske kontroller. {review_count} produkter er merket for kontroll. Prisgap, butikkposisjon og andel billigst utelater kontrollproduktene.", LIGHT)
    top = result.brands.sort_values(["comparable", "brand"], ascending=[False, True]).head(3)
    top_text = "; ".join(f"{r.brand}: {r.comparable} sammenlignbare av {r.products}" for r in top.itertuples())
    _block(ws, "A17", "L18", "Størst sammenligningsgrunnlag: " + top_text + ". Brandene kan ha svært ulik dekning.")
    _block(ws, "A19", "L20", f"{s['single_stock']} produkter er registrert på lager hos bare én butikk; {s['no_stock']} har ingen observerte tilbud på lager. Se Tilgjengelighet for produkt- og butikkspesifikke funn.", LIGHT)
    _block(ws, "A22", "L22", "Prioritert oppfølging", BLUE, bold=True)
    _block(ws, "A23", "L25", "1. Kontroller flaggede produktvarianter, GTIN-er og ekstreme priser i Prisgap.\n2. Undersøk de største beregnede prisgapene og butikkposisjonen innen hvert brand.\n3. Følg opp produkter uten lager og produkter med bare én observert lagerførende butikk.", GOLD)
    _block(ws, "A27", "L27", "Slik er sammenligningene avgrenset", BLUE, bold=True)
    _block(ws, "A28", "L30", f"Laveste kvalifiserende tilbud per produkt og butikk teller én gang. Prisgap er høyeste/laveste pris minus 1. Butikkposisjon krever minst {config.min_peer_stores} øvrige butikker. Prisratio over {config.extreme_price_ratio:g} utløser kontroll, ikke en konklusjon om feil. Lagerandel følger kildens status, også for produkter til kontroll.")
    _block(ws, "A32", "L34", "Rapporten beskriver observerte oppføringer på Prisradar, ikke komplett sortiment, markedsandel, salg eller margin. Produkter kan være størrelsesvarianter. Automatiske kontroller bekrefter ikke at alle tilbud gjelder identisk vare/pakning. Leverandørtilknytningen kommer fra uttrekket og dokumenterer ikke brandeierskap.", LIGHT)
    _block(ws, "A36", "L38", f"Førpris finnes på {s['before_price_rows']} av {s['offers']} tilbudsrader; manglende førpris betyr ukjent kampanjestatus. Førpris er ikke historisk prisbevis. Frakt finnes på {s['shipping_rows']} tilbudsrader og er utelatt fra prisanalysen. Direkte butikklenke finnes på {s['retailer_url_rows']} tilbudsrader.")
    _block(ws, "A40", "L42", "Siste snapshot velges separat per produkt; tidspunkter vises i detaljlistene. Dette er ingen trendanalyse. Produkter uten prisgrunnlag vises som Ikke beregnbart. Hele observasjonsgrunnlaget og årsaker til priseksklusjon følger i rapportens .observations.jsonl-fil.", LIGHT)
    _block(ws, "A44", "L44", "Måltall og definisjoner", BLUE, bold=True)
    for start, end, value, note in [
        ("A45", "C45", "Måltall", "Navn på måltall eller kildeopplysning."),
        ("D45", "E45", "Verdi", "Beregnet verdi i denne leverandørrapporten."),
        ("F45", "L45", "Definisjon / kilde", "Nevner, avgrensning eller kilde for måltallet."),
    ]:
        _header(_block(ws, start, end, value, INK, size=10), note)
    entries = [(COLUMNS[k][0], s[k], COLUMNS[k][1], COLUMNS[k][2]) for k in KPI_KEYS + ["review_products"]]
    entries += [("Periode start", s["period_start"], "Tidligste valgte produktsnapshot (UTC).", "text"),
                ("Periode slutt", s["period_end"], "Seneste valgte produktsnapshot (UTC).", "text"),
                ("Kilde", Path(s["source_file"]).name, "Råfilen er ikke endret. Kildehash står i JSON-manifestet.", "text")]
    for row, (label, value, definition, kind) in enumerate(entries, 46):
        fill = GREY if row % 2 else LIGHT
        _block(ws, f"A{row}", f"C{row}", label, fill, size=10, bold=True)
        cell = _block(ws, f"D{row}", f"E{row}", value if value is not None else NA, fill, size=10)
        cell.number_format = "0.0%" if kind == "pct" else ("#,##0" if kind == "count" else "General")
        _block(ws, f"F{row}", f"L{row}", definition, fill, size=10)
        ws.row_dimensions[row].height = 48
    ws.freeze_panes = "A4"
    ws.print_area = "A1:L57"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0


def build_report(result: BrandResult, config: BrandConfig, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.creator = "Auto Analyse"
    wb.properties.title = config.title + " – " + result.summary["supplier"]
    for n, (name, (attribute, keys)) in enumerate(SHEETS.items(), 1):
        _table(wb, name, getattr(result, attribute), keys, config, n)
    _dashboard(wb, result, config)
    ws = wb.create_sheet("Kolonneforklaringer")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"
    for col, (label, note, width) in enumerate([
        ("Ark", "Rapportfanen definisjonen gjelder.", 28),
        ("Kolonne", "Synlig kolonneoverskrift eller KPI-navn.", 32),
        ("Betyr", "Definisjon, nevner og avgrensning.", 100),
    ], 1):
        _header(_put(ws, 1, col, label), note)
        ws.column_dimensions[get_column_letter(col)].width = width
    definitions = [(sheet, COLUMNS[k][0], COLUMNS[k][1]) for sheet, (_, keys) in SHEETS.items() for k in keys]
    definitions += [("Analyse & oppsummering", COLUMNS[k][0], COLUMNS[k][1]) for k in KPI_KEYS]
    for row, values in enumerate(definitions, 2):
        for col, value in enumerate(values, 1):
            cell = _put(ws, row, col, value)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.fill = PatternFill("solid", fgColor=LIGHT if row % 2 == 0 else GREY)
        ws.row_dimensions[row].height = 48
    ws.row_dimensions[1].height = 30
    ws.auto_filter.ref = f"A1:C{len(definitions)+1}"
    wb.active = wb.sheetnames.index("Analyse & oppsummering")
    wb.save(output)
    wb.close()
    return output


def header_note_specs() -> list[dict]:
    notes = [{"sheet": sheet, "cell": f"{get_column_letter(col)}1", "header": COLUMNS[key][0], "note": COLUMNS[key][1]}
             for sheet, (_, keys) in SHEETS.items() for col, key in enumerate(keys, 1)]
    for col, header, note in [("A", "Ark", "Rapportfanen definisjonen gjelder."), ("B", "Kolonne", "Synlig kolonneoverskrift eller KPI-navn."), ("C", "Betyr", "Definisjon, nevner og avgrensning.")]:
        notes.append({"sheet": "Kolonneforklaringer", "cell": col + "1", "header": header, "note": note})
    for cell, header, note in [("A45", "Måltall", "Navn på måltall eller kildeopplysning."), ("D45", "Verdi", "Beregnet verdi i denne leverandørrapporten."), ("F45", "Definisjon / kilde", "Nevner, avgrensning eller kilde for måltallet.")]:
        notes.append({"sheet": "Analyse & oppsummering", "cell": cell, "header": header, "note": note})
    return notes
