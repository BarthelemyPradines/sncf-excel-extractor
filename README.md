# Excel Extractor

Analyzes `.xlsx` workbooks: detects sub-tables, extracts media, renders charts, and exports to CSV.

## Install

```bash
uv sync
```

Optional faster backend:

```bash
uv add python-calamine
```

## Usage

### CLI

```bash
uv run excel-extractor input.xlsx csv_out
```

### Python

```python
from excel_extractor import analyze_workbook, export_sub_tables_to_csv, render_charts_to_png

report = analyze_workbook("input.xlsx")
csvs = export_sub_tables_to_csv(report, out_dir="csv_out")
pngs = render_charts_to_png("input.xlsx", report.extracted_charts, "csv_out/charts",
                            values_by_sheet=report.values_by_sheet)
```

## Project Structure

```
src/excel_extractor/
  models.py      Data classes and shared helpers
  scanner.py     Sheet scanning (openpyxl + calamine)
  detection.py   Sub-table detection and classification
  media.py       Zip metadata and media extraction
  charts.py      Chart parsing and PNG rendering
  export.py      CSV export
  analyzer.py    Top-level orchestrator
  cli.py         CLI entry point
```
