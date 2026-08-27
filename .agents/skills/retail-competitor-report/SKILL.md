---
name: retail-competitor-report
description: Build and verify the repo's standard Flisekompaniet/Prisradar Excel insight report from a new crawl CSV, ZIP, or XLSX. Use when a user uploads similar raw price and availability data, asks for the same competitor analysis, or asks to refresh the report. Do not use for unrelated spreadsheets or custom one-off analyses.
---

# Retail Competitor Report

Produce the versioned seven-sheet report through the repository CLI. Do not reimplement the calculations in an ad hoc notebook.

## Workflow

1. Identify the input file.
   - Prefer an explicitly named file.
   - Otherwise use the newest supported file in `data/inbox/`.
   - Use `examples/raw/` only for a requested demonstration or when the inbox is empty.
2. Preserve the raw file. Do not edit, normalize, or overwrite it in place.
3. Ensure the project is installed with `python -m pip install -e .` when dependencies are missing.
4. Run `python -m auto_analyse <input>`; omit `<input>` only when automatic newest-file discovery is intended.
5. Run `python -m unittest discover -s tests -v` when code, configuration, layout, or examples changed. For an ordinary report refresh, inspect the generated JSON manifest and workbook structure instead of modifying the implementation.
6. Return the generated `.xlsx` from `outputs/` and summarize the input period plus the eight KPI cards. State the external-market-data caveat; do not invent sales or margin impact.

## Contract boundaries

- Keep the seven sheet names, column order, thresholds, number formats, and summary layout stable.
- Do not add charts or restore removed sheets.
- Treat `config/report.toml` as the supported customization surface.
- If the input schema is incompatible, stop with the CLI's missing-column list instead of guessing mappings.
- Read [references/report-contract.md](references/report-contract.md) before changing calculations, columns, thresholds, or layout.
