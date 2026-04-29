# Excel Extractor

Analyzes `.xlsx` workbooks: detects sub-tables, evaluates formulas, extracts charts/images, and exports to CSV.

## Install

```bash
uv sync
```

## Usage

### CLI

```bash
uv run excel-extractor input.xlsx output
```

This creates a structured output folder:

```
output/input/
  SimpleSheet.csv                   # trivial sheet -> flat CSV
  ComplexSheet/                     # multi-table or has charts/images
    ComplexSheet__t1_A1:B10.csv
    ComplexSheet__t2_D1:E10.csv
    charts/
      ComplexSheet__chart1.csv      # chart data
      ComplexSheet__chart1.png      # chart render
    images/
      image1.png
```

### Options

```bash
# Show raw formulas instead of computed values
uv run excel-extractor input.xlsx output --no-formula-results
```

### Python

```python
from excel_extractor import analyze_workbook, export_sheet_to_csv, export_charts_to_csv

report = analyze_workbook("input.xlsx")

# Export a single sheet
export_sheet_to_csv(report.sheets[0], report.values_by_sheet["Sheet1"], out_dir="out")

# Export chart data as CSV
export_charts_to_csv("input.xlsx", report.extracted_charts, out_dir="out/charts",
                     values_by_sheet=report.values_by_sheet)
```

## Project Structure

```
src/excel_extractor/
  models.py      Data classes and shared helpers
  scanner.py     Sheet scanning (openpyxl)
  detection.py   Sub-table detection and classification
  media.py       Zip metadata, media/image extraction
  charts.py      Chart parsing, PNG rendering, chart CSV export
  export.py      Sub-table CSV export
  analyzer.py    Top-level orchestrator + formula evaluation
  cli.py         CLI entry point
```
