"""CLI entry point for the excel extractor."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .analyzer import analyze_workbook
from .export import export_sheet_to_csv
from .charts import render_charts_to_png, export_charts_to_csv
from .media import chart_to_sheet_map, image_to_sheet_map, extract_images_for_sheet
from .models import safe_name


def _sheet_is_simple(sheet, chart_map: dict, image_map: dict) -> bool:
    """A sheet is simple if it has one sub-table (or less), no charts, no images."""
    has_charts = bool(chart_map.get(sheet.name))
    has_images = bool(image_map.get(sheet.name))
    multi_table = len(sheet.sub_tables) > 1
    return not has_charts and not has_images and not multi_table


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    src = args[0] if len(args) > 0 else "input.xlsx"
    out_base = args[1] if len(args) > 1 else "output"
    formula_results = "--no-formula-results" not in flags

    xlsx_path = Path(src)
    root_dir = Path(out_base) / xlsx_path.stem

    t0 = time.time()
    rep = analyze_workbook(src, formula_results=formula_results)
    print(f"Analyzed in {time.time() - t0:.2f}s")

    chart_map = chart_to_sheet_map(src)
    image_map = image_to_sheet_map(src)

    # Build a lookup: chart basename -> extracted xml path
    chart_xml_by_name: dict[str, str] = {}
    for p in rep.extracted_charts:
        chart_xml_by_name[Path(p).name] = p

    all_written: list[str] = []

    for sheet in rep.sheets:
        if sheet.classification == "empty":
            continue

        values = rep.values_by_sheet.get(sheet.name)
        if not values:
            continue

        sname = safe_name(sheet.name)

        if _sheet_is_simple(sheet, chart_map, image_map):
            # Simple sheet: flat CSV at root level
            csvs = export_sheet_to_csv(sheet, values, root_dir)
            # Rename to just <sheet_name>.csv if single table
            if len(csvs) == 1:
                old = Path(csvs[0])
                new = root_dir / f"{sname}.csv"
                old.rename(new)
                csvs = [str(new)]
            all_written.extend(csvs)
        else:
            # Complex sheet: create a folder
            sheet_dir = root_dir / sname

            # Sub-table CSVs
            csvs = export_sheet_to_csv(sheet, values, sheet_dir)
            all_written.extend(csvs)

            # Charts
            sheet_charts = chart_map.get(sheet.name, [])
            if sheet_charts:
                chart_dir = sheet_dir / "charts"
                chart_xmls = [chart_xml_by_name[c] for c in sheet_charts
                              if c in chart_xml_by_name]
                if chart_xmls:
                    chart_csvs = export_charts_to_csv(
                        src, chart_xmls, chart_dir,
                        values_by_sheet=rep.values_by_sheet)
                    all_written.extend(chart_csvs)

                    pngs = render_charts_to_png(
                        src, chart_xmls, chart_dir,
                        values_by_sheet=rep.values_by_sheet)
                    all_written.extend(pngs)

            # Images
            sheet_images = image_map.get(sheet.name, [])
            if sheet_images:
                image_dir = sheet_dir / "images"
                imgs = extract_images_for_sheet(src, sheet_images, image_dir)
                all_written.extend(imgs)

    print(f"\nOutput: {root_dir}/")
    for p in all_written:
        rel = Path(p).relative_to(root_dir)
        print(f"  {rel}")

    print(f"\nTotal: {len(all_written)} file(s)")

    print()
    print(json.dumps({
        "sheets": [
            {
                "name": s.name,
                "classification": s.classification,
                "size": f"{s.n_rows}x{s.n_cols}",
                "filled": s.n_filled,
                "sub_tables": [t.excel_range() for t in s.sub_tables],
                "notes": s.notes,
            }
            for s in rep.sheets
        ],
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
