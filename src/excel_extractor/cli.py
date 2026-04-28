"""CLI entry point for the excel extractor."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .analyzer import analyze_workbook, HAVE_CALAMINE
from .export import export_sub_tables_to_csv
from .charts import render_charts_to_png


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else "input.xlsx"
    out = sys.argv[2] if len(sys.argv) > 2 else "csv_out"

    t0 = time.time()
    rep = analyze_workbook(src)
    print(f"Analyzed in {time.time() - t0:.2f}s "
          f"(calamine={'yes' if HAVE_CALAMINE else 'no'})")

    csvs = export_sub_tables_to_csv(rep, out_dir=out)
    print(f"Wrote {len(csvs)} CSV(s) to {out}/")
    for p in csvs:
        print(f"  - {p}")

    if rep.extracted_charts:
        png_dir = Path(out) / "charts"
        pngs = render_charts_to_png(src, rep.extracted_charts, png_dir,
                                    values_by_sheet=rep.values_by_sheet)
        print(f"\nRendered {len(pngs)}/{len(rep.extracted_charts)} chart(s) to {png_dir}/")
        for p in pngs:
            print(f"  - {p}")

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
        "n_media": len(rep.extracted_media),
        "n_charts": len(rep.extracted_charts),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
