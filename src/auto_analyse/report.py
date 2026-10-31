from __future__ import annotations

from datetime import datetime
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter

from .analysis import AnalysisResult
from .config import AppConfig


INK = "0B1934"
BLUE_DARK = "264A96"
BLUE = "2563EB"
BLUE_LIGHT = "EAF2FF"
GOLD = "D97706"
GOLD_LIGHT = "FFF7ED"
GREY_LIGHT = "F8FAFC"
GREY = "D1D5DB"
SLATE = "475569"
WHITE = "FFFFFF"
FONT = "Carlito"
THIN_GREY = Side(style="thin", color=GREY)
BOX = Border(left=THIN_GREY, right=THIN_GREY, top=THIN_GREY, bottom=THIN_GREY)


CATEGORY_HEADERS = {
    "catalogue_category": "Produktkategori",
    "products": "Produkter",
    "matched_products": "Matchede produkter",
    "match_rate": "Matchgrad",
    "comparable_in_stock": "Sammenlignbare in-stock",
    "own_stock_rate": "Egen lagerandel",
    "competitor_stock_coverage": "Konkurrent lagerdekning",
    "price_leader_share": "Prislederandel",
    "above_5pct_share": "Andel >5 % over billigste",
    "above_15pct_share": "Andel >15 % over billigste",
    "median_gap_to_cheapest": "Median gap til billigste",
    "price_opportunities": "Prisvarsler",
    "availability_risks": "Tilgjengelighetsrisiko",
}

COMPETITOR_HEADERS = {
    "retailer_domain_norm": "Konkurrentdomene",
    "matched_products": "Matchede produkter",
    "in_stock_matches": "In-stock-matcher",
    "comparable_in_stock": "Sammenlignbare in-stock",
    "competitor_cheaper_share": "Konkurrent billigere",
    "own_cheaper_share": "Flisekompaniet billigere",
    "median_comp_price_gap": "Median konkurrentgap",
}

ACTION_HEADERS = {
    "product_id": "Produkt-ID",
    "gtin": "GTIN",
    "product_brand": "Merke",
    "model": "Produkt",
    "catalogue_category": "Kategori",
    "own_price": "Flisekompaniet-pris",
    "own_availability": "Flisekompaniet-status",
    "best_comp_price": "Beste konkurrentpris",
    "best_competitor": "Billigste konkurrent",
    "gap_to_min_nok": "Prisgap (NOK)",
    "gap_to_min_pct": "Prisgap (%)",
    "competitor_in_stock_count": "Konkurrenter in-stock",
    "own_url": "Flisekompaniet-URL",
    "best_competitor_url": "Konkurrent-URL",
}

CATEGORY_DEFINITIONS = {
    "Produktkategori": "Kategorien produktet er gruppert i (catalogue_category).",
    "Produkter": "Antall unike Flisekompaniet-produkter i siste snapshot.",
    "Matchede produkter": "Produkter med minst én konkurrentobservasjon på samme produkt-ID. Koblingen må være gjort før import.",
    "Matchgrad": "Matchede produkter delt på alle produkter i kategorien.",
    "Sammenlignbare in-stock": "Produkter der både Flisekompaniet og minst én konkurrent er registrert in_stock.",
    "Egen lagerandel": "Andel av Flisekompaniets produkter som er registrert in_stock.",
    "Konkurrent lagerdekning": "Andel produkter der minst én konkurrent er registrert in_stock.",
    "Prislederandel": "Andel sammenlignbare produkter der Flisekompaniets pris er innenfor 1 % av billigste konkurrent.",
    "Andel >5 % over billigste": "Andel sammenlignbare produkter med egen pris mer enn 5 % over billigste tilgjengelige konkurrent.",
    "Andel >15 % over billigste": "Andel sammenlignbare produkter med egen pris mer enn 15 % over billigste tilgjengelige konkurrent.",
    "Median gap til billigste": "Median prosentvis prisforskjell mellom Flisekompaniet og billigste tilgjengelige konkurrent.",
    "Prisvarsler": "Antall produkter der egen pris er mer enn 5 % over billigste tilgjengelige konkurrent.",
    "Tilgjengelighetsrisiko": "Antall produkter der Flisekompaniet ikke er in_stock, mens minst én konkurrent er in_stock.",
}

COMPETITOR_DEFINITIONS = {
    "Konkurrentdomene": "Nettstedet observasjonen kommer fra.",
    "Matchede produkter": "Antall Flisekompaniet-produkter med observasjon hos konkurrenten.",
    "In-stock-matcher": "Matchede produkter der konkurrenten er registrert in_stock.",
    "Sammenlignbare in-stock": "Produkter der både Flisekompaniet og konkurrenten er registrert in_stock.",
    "Konkurrent billigere": "Andel sammenlignbare produkter der konkurrentens pris er mer enn 1 % lavere.",
    "Flisekompaniet billigere": "Andel sammenlignbare produkter der Flisekompaniets pris er mer enn 1 % lavere.",
    "Median konkurrentgap": "Median prosentvis prisforskjell: konkurrentpris mot Flisekompaniet-pris.",
}

ACTION_DEFINITIONS = {
    "Produkt-ID": "Flisekompaniets interne produkt-ID.",
    "GTIN": "Global Trade Item Number fra kilden. Rapporten kobler rader på produkt-ID, ikke automatisk på GTIN.",
    "Merke": "Produktets merke.",
    "Produkt": "Produktnavn hos Flisekompaniet.",
    "Kategori": "Produktets catalogue_category.",
    "Flisekompaniet-pris": "Observert salgspris hos Flisekompaniet i siste snapshot.",
    "Flisekompaniet-status": "Observert availability_status hos Flisekompaniet.",
    "Beste konkurrentpris": "Laveste observerte pris blant tilgjengelige konkurrenter.",
    "Billigste konkurrent": "Aktøren med laveste tilgjengelige konkurrentpris.",
    "Prisgap (NOK)": "Flisekompaniet-pris minus beste konkurrentpris.",
    "Prisgap (%)": "Prisgap i NOK delt på beste konkurrentpris.",
    "Konkurrenter in-stock": "Antall konkurrenter som er registrert in_stock for produktet.",
    "Flisekompaniet-URL": "Direktelenke til produktet hos Flisekompaniet.",
    "Konkurrent-URL": "Direktelenke til billigste tilgjengelige konkurrent.",
}


def _report_text(text: str, config: AppConfig) -> str:
    """Format report-owned labels, never rewrite raw product names or URLs."""
    m = config.monitoring
    pct = lambda value: f"{100 * value:g}".replace(".", ",")
    replacements = {
        "Flisekompaniet": config.retailer.name,
        "NOK": m.currency,
        "in_stock": m.in_stock_value,
        "5 % under": f"{pct(abs(m.underpricing_threshold))} % under",
        "5/15 %": f"{pct(m.price_alert_threshold)}/{pct(m.critical_price_alert_threshold)} %",
        "15 %": f"{pct(m.critical_price_alert_threshold)} %",
        "5 %": f"{pct(m.price_alert_threshold)} %",
        "1 %": f"{pct(m.price_leader_tolerance)} %",
    }
    return re.sub("|".join(re.escape(key) for key in replacements), lambda match: replacements[match[0]], text)


def _labels(mapping: dict[str, str], config: AppConfig) -> dict[str, str]:
    return {_report_text(key, config): _report_text(value, config) for key, value in mapping.items()}


def _headers(mapping: dict[str, str], config: AppConfig) -> dict[str, str]:
    return {key: _report_text(value, config) for key, value in mapping.items()}


def header_note_specs(config: AppConfig | None = None) -> list[dict[str, str]]:
    """Shared Excel/Google Sheets notes, bound to exact header labels."""
    specs = []
    for sheet, definitions in [
        ("Kategorier", CATEGORY_DEFINITIONS),
        ("Konkurrenter", COMPETITOR_DEFINITIONS),
        ("Prisvarsler", ACTION_DEFINITIONS),
        ("Tilgjengelighetsrisiko", ACTION_DEFINITIONS),
        ("Marginvakt", ACTION_DEFINITIONS),
        ("Kolonneforklaringer", {
            "Ark": "Rapportfanen kolonnen tilhører.",
            "Kolonne": "Kolonneoverskriften slik den vises i den aktuelle rapportfanen.",
            "Betyr": "Forklaring av kolonnens innhold eller beregningsmåte.",
        }),
    ]:
        for column, (header, note) in enumerate(definitions.items(), start=1):
            specs.append({"sheet": sheet, "cell": f"{get_column_letter(column)}1", "header": header, "note": note})
    for cell, header, note in [
        ("A45", "Måltall", "Navnet på nøkkeltallet eller opplysningen som oppsummeres."),
        ("D45", "Verdi", "Beregnet verdi for måltallet, eller oppgitt periode og kilde."),
        ("F45", "Definisjon / kilde", "Beregningsgrunnlag, avgrensning eller kilde for måltallet."),
    ]:
        specs.append({"sheet": "Analyse & oppsummering", "cell": cell, "header": header, "note": note})
    config = config or AppConfig()
    return [{**spec, "header": _report_text(spec["header"], config), "note": _report_text(spec["note"], config)} for spec in specs]


def add_header_notes(wb: Workbook, config: AppConfig) -> None:
    """Add legacy Excel notes without changing values or formatting."""
    for spec in header_note_specs(config):
        cell = wb[spec["sheet"]][spec["cell"]]
        if cell.value != spec["header"]:
            raise ValueError(f"Uventet kolonneoverskrift: {spec['sheet']}!{spec['cell']}")
        cell.comment = Comment(spec["note"], "Auto Analyse")
        cell.comment.width = 360
        cell.comment.height = 100


def _value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def _header_style(cell) -> None:
    cell.fill = PatternFill("solid", fgColor=INK)
    cell.font = Font(name=FONT, bold=True, color=WHITE, size=10)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BOX


def _section_header(ws, cell_range: str, text: str) -> None:
    ws.merge_cells(cell_range)
    cell = ws[cell_range.split(":")[0]]
    cell.value = text
    cell.fill = PatternFill("solid", fgColor=BLUE_DARK)
    cell.font = Font(name=FONT, bold=True, color=WHITE, size=13)
    cell.alignment = Alignment(vertical="center")
    cell.border = BOX
    ws.row_dimensions[cell.row].height = 26


def _callout(ws, cell_range: str, text: str, fill: str = GREY_LIGHT, *, center: bool = False) -> None:
    ws.merge_cells(cell_range)
    cell = ws[cell_range.split(":")[0]]
    cell.value = text
    cell.fill = PatternFill("solid", fgColor=fill)
    cell.font = Font(name=FONT, color=INK, bold=center, size=10)
    cell.alignment = Alignment(
        vertical="center", horizontal="center" if center else "left", wrap_text=True
    )
    cell.border = BOX


def _write_dataframe(ws, frame: pd.DataFrame, headers: dict[str, str]) -> int:
    columns = list(headers)
    for index, column in enumerate(columns, start=1):
        ws.cell(1, index, headers[column])
        _header_style(ws.cell(1, index))
    ws.row_dimensions[1].height = 38
    for row_index, row in enumerate(frame[columns].itertuples(index=False, name=None), start=2):
        for column_index, raw in enumerate(row, start=1):
            cell = ws.cell(row_index, column_index, _value(raw))
            if isinstance(raw, str):
                cell.data_type = "s"
            cell.font = Font(name=FONT, size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=False)
            cell.border = Border(bottom=Side(style="hair", color="E5E7EB"))
    return max(1, len(frame) + 1)


def _add_table(ws, name: str, last_row: int, last_column: int) -> None:
    if last_row < 2:
        return
    table = Table(displayName=name, ref=f"A1:{get_column_letter(last_column)}{last_row}")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(table)


def _add_definition_panel(
    ws,
    start_row: int,
    end_column: int,
    definitions: dict[str, str],
    *,
    label_end_column: int,
) -> None:
    end_letter = get_column_letter(end_column)
    label_end = get_column_letter(label_end_column)
    text_start = get_column_letter(label_end_column + 1)
    _section_header(ws, f"A{start_row}:{end_letter}{start_row}", "Hva betyr kolonnene?")
    for offset, (label, definition) in enumerate(definitions.items(), start=1):
        row = start_row + offset
        ws.merge_cells(f"A{row}:{label_end}{row}")
        ws.merge_cells(f"{text_start}{row}:{end_letter}{row}")
        fill = GREY_LIGHT if offset % 2 else BLUE_LIGHT
        label_cell = ws[f"A{row}"]
        label_cell.value = label
        label_cell.font = Font(name=FONT, bold=True, color=INK, size=10)
        label_cell.fill = PatternFill("solid", fgColor=fill)
        label_cell.alignment = Alignment(vertical="center", wrap_text=True)
        label_cell.border = BOX
        definition_cell = ws[f"{text_start}{row}"]
        definition_cell.value = definition
        definition_cell.font = Font(name=FONT, color=SLATE, size=10)
        definition_cell.fill = PatternFill("solid", fgColor=fill)
        definition_cell.alignment = Alignment(vertical="center", wrap_text=True)
        definition_cell.border = BOX
        ws.row_dimensions[row].height = 30


def _prepare_category_sheet(wb: Workbook, result: AnalysisResult, config: AppConfig) -> None:
    ws = wb.create_sheet("Kategorier")
    last_row = _write_dataframe(ws, result.category_position, _headers(CATEGORY_HEADERS, config))
    _add_table(ws, "CategoryPositionTable", last_row, len(CATEGORY_HEADERS))
    widths = [30, 13, 16, 12, 18, 15, 19, 15, 20, 21, 19, 13, 20]
    for column, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(column)].width = width
    for row in range(2, last_row + 1):
        for column in [2, 3, 5, 12, 13]:
            ws.cell(row, column).number_format = "#,##0"
        for column in [4, 6, 7, 8, 9, 10, 11]:
            ws.cell(row, column).number_format = "0.0%"
    if last_row >= 2:
        ws.conditional_formatting.add(
            f"K2:K{last_row}",
            ColorScaleRule(
                start_type="min", start_color=BLUE_LIGHT,
                mid_type="percentile", mid_value=50, mid_color=GREY_LIGHT,
                end_type="max", end_color="FED7AA",
            ),
        )
        ws.conditional_formatting.add(
            f"L2:L{last_row}", DataBarRule(start_type="min", end_type="max", color=BLUE)
        )
        ws.conditional_formatting.add(
            f"M2:M{last_row}", DataBarRule(start_type="min", end_type="max", color=GOLD)
        )
    _add_definition_panel(
        ws, len(result.category_position) + 4, 13, _labels(CATEGORY_DEFINITIONS, config), label_end_column=4
    )
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:M{last_row}"
    ws.sheet_view.showGridLines = False


def _prepare_competitor_sheet(wb: Workbook, result: AnalysisResult, config: AppConfig) -> None:
    ws = wb.create_sheet("Konkurrenter")
    frame = result.competitor_position.drop(columns=["retailer_name"], errors="ignore")
    last_row = _write_dataframe(ws, frame, _headers(COMPETITOR_HEADERS, config))
    _add_table(ws, "CompetitorPositionTable", last_row, len(COMPETITOR_HEADERS))
    widths = [28, 18, 18, 21, 20, 22, 22]
    for column, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(column)].width = width
    for row in range(2, last_row + 1):
        for column in [2, 3, 4]:
            ws.cell(row, column).number_format = "#,##0"
        for column in [5, 6, 7]:
            ws.cell(row, column).number_format = "0.0%"
    if last_row >= 2:
        ws.conditional_formatting.add(
            f"E2:E{last_row}", DataBarRule(start_type="min", end_type="max", color=GOLD)
        )
    _add_definition_panel(
        ws, len(frame) + 8, 7, _labels(COMPETITOR_DEFINITIONS, config), label_end_column=1
    )
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{last_row}"
    ws.sheet_view.showGridLines = False


def _prepare_action_sheet(
    wb: Workbook,
    name: str,
    frame: pd.DataFrame,
    table_name: str,
    *,
    config: AppConfig,
    bar_color: str,
    availability_highlight: bool = False,
) -> None:
    ws = wb.create_sheet(name)
    last_row = _write_dataframe(ws, frame, _headers(ACTION_HEADERS, config))
    _add_table(ws, table_name, last_row, len(ACTION_HEADERS))
    widths = [14, 17, 18, 48, 28, 18, 20, 19, 24, 17, 15, 18, 55, 55]
    for column, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(column)].width = width
    for row in range(2, last_row + 1):
        for column in [6, 8, 10]:
            ws.cell(row, column).number_format = f'#,##0 "{config.monitoring.currency}"'
        ws.cell(row, 11).number_format = "0.0%"
        ws.cell(row, 12).number_format = "#,##0"
        for column in [13, 14]:
            cell = ws.cell(row, column)
            if isinstance(cell.value, str) and cell.value.startswith(("https://", "http://")):
                cell.hyperlink = str(cell.value)
                cell.style = "Hyperlink"
    if last_row >= 2:
        ws.conditional_formatting.add(
            f"K2:K{last_row}", DataBarRule(start_type="min", end_type="max", color=bar_color)
        )
        if availability_highlight:
            ws.conditional_formatting.add(
                f"G2:G{last_row}",
                FormulaRule(
                    formula=['ISNUMBER(SEARCH("out_of_stock",G2))'],
                    fill=PatternFill("solid", fgColor=GOLD_LIGHT),
                    font=Font(name=FONT, bold=True, color=GOLD),
                ),
            )
    ws.column_dimensions["O"].width = 3
    _section_header(
        ws,
        "P1:X1",
        "Hva betyr kolonnene? Se også arket «Kolonneforklaringer» for samlet oversikt.",
    )
    for offset, (label, definition) in enumerate(_labels(ACTION_DEFINITIONS, config).items(), start=2):
        ws.merge_cells(f"P{offset}:R{offset}")
        ws.merge_cells(f"S{offset}:X{offset}")
        fill = GREY_LIGHT if offset % 2 else BLUE_LIGHT
        left = ws[f"P{offset}"]
        left.value = label
        left.font = Font(name=FONT, bold=True, color=INK, size=10)
        left.fill = PatternFill("solid", fgColor=fill)
        left.alignment = Alignment(vertical="center", wrap_text=True)
        left.border = BOX
        right = ws[f"S{offset}"]
        right.value = definition
        right.font = Font(name=FONT, color=SLATE, size=10)
        right.fill = PatternFill("solid", fgColor=fill)
        right.alignment = Alignment(vertical="center", wrap_text=True)
        right.border = BOX
        ws.row_dimensions[offset].height = 30
    for column in range(16, 25):
        ws.column_dimensions[get_column_letter(column)].width = 13
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:N{last_row}"
    ws.sheet_view.showGridLines = False


def _nb_number(value: int | float) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}".replace(",", " ").replace(".", ",")
    return f"{int(value):,}".replace(",", " ")


def _pct(value: float) -> str:
    if not math.isfinite(value):
        return "Ikke beregnbart"
    return f"{value * 100:.1f}".replace(".", ",") + " %"


def _prepare_dashboard(wb: Workbook, result: AnalysisResult, config: AppConfig) -> None:
    ws = wb.create_sheet("Analyse & oppsummering")
    summary = result.summary

    def callout(sheet, cell_range, text, fill=GREY_LIGHT, *, center=False):
        _callout(sheet, cell_range, _report_text(text, config), fill, center=center)
    ws.sheet_view.showGridLines = False
    for column in range(1, 13):
        ws.column_dimensions[get_column_letter(column)].width = 13

    ws.merge_cells("A1:L1")
    ws["A1"] = _report_text(config.report.title, config)
    ws["A1"].fill = PatternFill("solid", fgColor=INK)
    ws["A1"].font = Font(name=FONT, bold=True, color=WHITE, size=20)
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 38

    ws.merge_cells("A2:L2")
    ws["A2"] = (
        f"Pilotdata {summary['period_start']}–{summary['period_end']} | "
        f"siste snapshot {summary['latest_date']} | {_nb_number(summary['raw_rows'])} råobservasjoner"
    )
    ws["A2"].fill = PatternFill("solid", fgColor=BLUE_LIGHT)
    ws["A2"].font = Font(name=FONT, bold=True, color=BLUE_DARK, size=11)
    ws["A2"].alignment = Alignment(vertical="center")
    ws.row_dimensions[2].height = 26

    def kpi(label_range: str, value_range: str, label: str, value: Any, number_format: str, fill: str) -> None:
        ws.merge_cells(label_range)
        ws.merge_cells(value_range)
        label_cell = ws[label_range.split(":")[0]]
        label_cell.value = _report_text(label, config)
        label_cell.fill = PatternFill("solid", fgColor=fill)
        label_cell.font = Font(name=FONT, bold=True, color=SLATE, size=10)
        label_cell.alignment = Alignment(horizontal="center", vertical="center")
        label_cell.border = BOX
        value_cell = ws[value_range.split(":")[0]]
        value_cell.value = _value(value)
        value_cell.fill = PatternFill("solid", fgColor=fill)
        value_cell.font = Font(name=FONT, bold=True, color=INK, size=22)
        value_cell.alignment = Alignment(horizontal="center", vertical="center")
        value_cell.border = BOX
        value_cell.number_format = number_format

    kpi("A4:C4", "A5:C6", "PRODUKTER OVERVÅKET", summary["target_products"], "#,##0", GREY_LIGHT)
    kpi("D4:F4", "D5:F6", "MATCHGRAD", summary["match_rate"], "0%", BLUE_LIGHT)
    kpi("G4:I4", "G5:I6", "SAMMENLIGNBARE IN-STOCK", summary["comparable_in_stock"], "#,##0", GREY_LIGHT)
    kpi("J4:L4", "J5:L6", "PRISLEDERANDEL", summary["price_leader_share"], "0%", BLUE_LIGHT)
    kpi("A8:C8", "A9:C10", "PRISVARSLER >5 %", summary["above_5pct_count"], "#,##0", GOLD_LIGHT)
    kpi("D8:F8", "D9:F10", "PRISVARSLER >15 %", summary["above_15pct_count"], "#,##0", GOLD_LIGHT)
    kpi("G8:I8", "G9:I10", "MEDIAN GAP TIL BILLIGSTE", summary["median_gap_to_cheapest"], "0%", GOLD_LIGHT)
    kpi("J8:L8", "J9:L10", "TILGJENGELIGHETSRISIKO", summary["availability_risk_count"], "#,##0", GOLD_LIGHT)

    _section_header(ws, "A12:L12", "Hva pilotdataene sier")
    callout(
        ws,
        "A13:L14",
        f"Prisbildet er bredt nok til å prioritere: {_nb_number(summary['above_5pct_count'])} av "
        f"{_nb_number(summary['comparable_in_stock'])} sammenlignbare lagerførte produkter "
        f"({_pct(summary['above_5pct_share'])}) ligger mer enn 5 % over billigste tilgjengelige "
        f"konkurrent. Medianen er {_pct(summary['median_gap_to_cheapest'])} over billigste og "
        f"{_pct(summary['median_gap_to_market'])} over markedsmedianen.",
        GOLD_LIGHT,
    )
    callout(
        ws,
        "A15:L16",
        f"Tilgjengelighet er et like stort kommersielt signal: {_nb_number(summary['availability_risk_count'])} "
        f"produkter var ikke «in_stock» hos {config.retailer.name} mens minst én konkurrent var det. "
        f"{summary['top_risk_category']} alene står for {_nb_number(summary['top_risk_category_count'])} slike produktgap.",
    )
    callout(
        ws,
        "A17:L18",
        f"Markedet flytter seg i løpet av perioden: {_nb_number(summary['own_price_changed_products'])} egne priser "
        f"og {_nb_number(summary['competitor_best_price_changed_products'])} billigste markedspriser endret seg. "
        f"Billigste konkurrent skiftet for {_nb_number(summary['best_competitor_changed_products'])} produkter "
        f"på de sammenlignbare Prisradar-dagene.",
        BLUE_LIGHT,
    )
    callout(
        ws,
        "A19:L20",
        f"{_nb_number(summary['underpricing_watch_count'])} produkter lå mer enn 5 % under alle tilgjengelige "
        "konkurrenter. Det er ikke et automatisk signal om prisøkning, men en konkret marginvakt som kan "
        "kombineres med salg, lager og margin.",
    )

    _section_header(ws, "A22:L22", "Forslag til pitch: selg beslutningshastighet, ikke bare data")
    callout(
        ws,
        "A23:L24",
        "«Vi gir dere en daglig prioritert arbeidsliste over hvor pris eller tilgjengelighet faktisk kan koste "
        "trafikk og konvertering – og hvor dere kan beskytte margin. Alt kan spores til produkt, kategori og konkurrent.»",
        BLUE_LIGHT,
    )
    cards = [
        ("A26:C29", "1. Daglige varsler\nPris >5/15 %, lagergap og prislederbytte"),
        ("D26:F29", "2. Ukentlig scorecard\nKategori, konkurrent og markedsbevegelse"),
        ("G26:I29", "3. Produktlister\nGTIN, prisgap, konkurrent og kilde-URL"),
        ("J26:L29", "4. Produksjons-SLA\nFerskhet, dekning, duplikater og feilvarsling"),
    ]
    for cell_range, text in cards:
        callout(ws, cell_range, text, GREY_LIGHT, center=True)

    score = result.category_position.assign(
        action_score=result.category_position["price_opportunities"]
        + result.category_position["availability_risks"]
    )
    top_categories = [
        str(value)
        for value in score.sort_values("action_score", ascending=False)
        .head(config.report.pilot_category_count)["catalogue_category"]
        .tolist()
    ]
    _section_header(ws, "A31:L31", "Anbefalt neste steg")
    callout(
        ws,
        "A32:L33",
        f"Kjør en {config.report.pilot_days}-dagers pilot i de største handlingskategoriene: "
        f"{', '.join(top_categories)}. Lever daglige produktvarsler og en ukentlig lederoppsummering; "
        "koble deretter mot interne salg-, margin- og lagerdata for å rangere økonomisk effekt.",
        GOLD_LIGHT,
    )
    missing_text = (
        "Ingen sammenlignbare Prisradar-dager mangler"
        if not summary["missing_prisradar_dates"]
        else "Prisradar-kjøring mangler " + ", ".join(summary["missing_prisradar_dates"])
    )
    callout(
        ws,
        "A35:L37",
        f"Viktig for pitchen: dette er et {len(pd.date_range(summary['period_start'], summary['period_end']))}-dagers "
        f"utvendig markedssnapshot, ikke et estimat på omsetning eller margin. {missing_text}, førpris er fylt på "
        f"{_pct(summary['before_price_coverage'])} av radene, og webstatus er ikke det samme som butikk- eller "
        "leveringslager. Matchingen forutsetter at lik GTIN/produkt-ID betyr samme salgbare enhet; pakningsstørrelse, "
        "frakt og variant bør spottsjekkes før automatisk reprising. Funnene er klare nok til å begrunne en pilot, "
        "men bør presenteres med disse forbeholdene.",
    )

    _section_header(ws, "A39:L39", "Slik leses arket")
    callout(
        ws,
        "A40:L42",
        "KPI-kortene øverst oppsummerer siste snapshot. Midtseksjonen forklarer de viktigste funnene, mens de "
        "nederste seksjonene foreslår leveranse og neste steg. Måltall og definisjoner er samlet i tabellen nederst "
        "i dette arket. Alle øvrige tabellkolonner er forklart i «Kolonneforklaringer».",
    )
    _section_header(ws, "A44:L44", "Måltall og definisjoner")

    metric_rows: list[tuple[str, Any, str, str]] = [
        ("Produkter overvåket", summary["target_products"], "Unike Flisekompaniet-produkt-IDer i siste snapshot", "count"),
        ("Matchgrad", summary["match_rate"], "Andel produkter med minst én konkurrentobservasjon", "pct"),
        ("Sammenlignbare lagerførte produkter", summary["comparable_in_stock"], "Flisekompaniet og minst én konkurrent er in_stock", "count"),
        ("Prislederandel", summary["price_leader_share"], "Egen pris innenfor 1 % av billigste tilgjengelige konkurrent", "pct"),
        ("Prisvarsler >5 %", summary["above_5pct_count"], "Egen pris mer enn 5 % over billigste tilgjengelige konkurrent", "count"),
        ("Prisvarsler >15 %", summary["above_15pct_count"], "Egen pris mer enn 15 % over billigste tilgjengelige konkurrent", "count"),
        ("Median gap til billigste", summary["median_gap_to_cheapest"], "Median på sammenlignbare produkter i siste snapshot", "pct"),
        ("Tilgjengelighetsrisiko", summary["availability_risk_count"], "Flisekompaniet ikke in_stock, mens minst én konkurrent er in_stock", "count"),
        ("Egen lagerandel", summary["own_stock_rate"], "Andel Flisekompaniet-produkter merket in_stock", "pct"),
        ("Konkurrent lagerdekning", summary["competitor_stock_coverage"], "Andel produkter der minst én konkurrent er in_stock", "pct"),
        ("Marginvakt", summary["underpricing_watch_count"], "Egen pris mer enn 5 % under alle tilgjengelige konkurrenter", "count"),
        ("Markedspris endret", summary["competitor_best_price_changed_products"], "Produkter der billigste markedspris endret seg på sammenlignbare Prisradar-dager", "count"),
        ("Egen pris endret", summary["own_price_changed_products"], "Produkter med mer enn én observert Flisekompaniet-pris i perioden", "count"),
        ("Prisleder endret", summary["best_competitor_changed_products"], "Produkter der billigste konkurrent endret seg på sammenlignbare Prisradar-dager", "count"),
        ("Median gap til markedsmedian", summary["median_gap_to_market"], "Egen pris mot median tilgjengelig konkurrentpris", "pct"),
        ("Sum synlige enhetsprisgap", summary["listed_unit_gap_nok"], "Sum prisdifferanse per produkt; ikke et omsetnings- eller marginestimat", "currency"),
        ("Periode start", summary["period_start"], "UTC-dato", "text"),
        ("Periode slutt", summary["period_end"], "UTC-dato", "text"),
        ("Råobservasjoner", summary["raw_rows"], "Antall rader i kildefilen", "count"),
        ("Kilde", summary["source_file"], "Klikk på filnavnet for å åpne kilden.", "source"),
    ]
    headers = [
        ("A45:C45", "Måltall"),
        ("D45:E45", "Verdi"),
        ("F45:L45", "Definisjon / kilde"),
    ]
    for cell_range, label in headers:
        ws.merge_cells(cell_range)
        cell = ws[cell_range.split(":")[0]]
        cell.value = label
        _header_style(cell)
    for index, (label, value, definition, kind) in enumerate(metric_rows, start=46):
        ws.merge_cells(f"A{index}:C{index}")
        ws.merge_cells(f"D{index}:E{index}")
        ws.merge_cells(f"F{index}:L{index}")
        fill = GREY_LIGHT if index % 2 == 0 else BLUE_LIGHT
        for anchor, cell_value in [
            (f"A{index}", _report_text(label, config)),
            (f"D{index}", _value(value)),
            (f"F{index}", _report_text(definition, config)),
        ]:
            cell = ws[anchor]
            cell.value = cell_value
            cell.fill = PatternFill("solid", fgColor=fill)
            cell.border = BOX
            cell.font = Font(name=FONT, bold=anchor.startswith("A"), color=INK, size=10)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        value_cell = ws[f"D{index}"]
        value_cell.alignment = Alignment(horizontal="right", vertical="center")
        value_cell.number_format = {
            "count": "#,##0",
            "pct": "0%",
            "currency": f'#,##0 "{config.monitoring.currency}"',
        }.get(kind, "General")
        if kind == "source" and summary["source_url"]:
            value_cell.hyperlink = summary["source_url"]
            value_cell.font = Font(name=FONT, color="0563C1", underline="single", size=10)
        ws.row_dimensions[index].height = 28

    ws.freeze_panes = "A3"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_area = "A1:L65"


def _prepare_glossary(wb: Workbook, config: AppConfig) -> None:
    ws = wb.create_sheet("Kolonneforklaringer")
    rows: list[tuple[str, str, str]] = []
    for sheet, definitions in [
        ("Kategorier", CATEGORY_DEFINITIONS),
        ("Konkurrenter", COMPETITOR_DEFINITIONS),
        ("Prisvarsler", ACTION_DEFINITIONS),
        ("Tilgjengelighetsrisiko", ACTION_DEFINITIONS),
        ("Marginvakt", ACTION_DEFINITIONS),
    ]:
        rows.extend((sheet, column, definition) for column, definition in _labels(definitions, config).items())
    for column, header in enumerate(["Ark", "Kolonne", "Betyr"], start=1):
        ws.cell(1, column, header)
        _header_style(ws.cell(1, column))
    for row_index, row in enumerate(rows, start=2):
        for column_index, value in enumerate(row, start=1):
            cell = ws.cell(row_index, column_index, value)
            cell.font = Font(name=FONT, size=10, bold=column_index < 3)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.fill = PatternFill(
                "solid", fgColor=GREY_LIGHT if row_index % 2 == 0 else BLUE_LIGHT
            )
            cell.border = Border(bottom=Side(style="hair", color="E5E7EB"))
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 92
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:C{len(rows) + 1}"
    ws.sheet_view.showGridLines = False


def build_report(result: AnalysisResult, config: AppConfig, output_path: str | Path) -> Path:
    """Build the fixed seven-sheet Excel insight report."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.creator = "Auto Analyse"
    wb.properties.title = _report_text(config.report.title, config)
    wb.properties.subject = "Pris- og tilgjengelighetsanalyse"
    wb.properties.created = datetime.now()

    _prepare_category_sheet(wb, result, config)
    _prepare_competitor_sheet(wb, result, config)
    _prepare_action_sheet(
        wb, "Prisvarsler", result.price_opportunities, "PriceAlertsTable", bar_color=GOLD, config=config
    )
    _prepare_action_sheet(
        wb,
        "Tilgjengelighetsrisiko",
        result.availability_risks,
        "AvailabilityRisksTable",
        bar_color=GOLD,
        config=config,
        availability_highlight=True,
    )
    _prepare_action_sheet(
        wb, "Marginvakt", result.underpricing_watch, "MarginWatchTable", bar_color=BLUE, config=config
    )
    _prepare_dashboard(wb, result, config)
    _prepare_glossary(wb, config)
    add_header_notes(wb, config)
    wb.active = wb.sheetnames.index("Analyse & oppsummering")
    wb.save(output)
    return output
