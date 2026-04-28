"""CSV export of detected sub-tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import SubTable, WorkbookReport, is_blank, safe_name


def export_sub_tables_to_csv(report: WorkbookReport,
                             out_dir: str | Path,
                             include_computational: bool = False,
                             header_rows: int | None = None) -> list[str]:
    """
    Write each detected sub-table to its own CSV.
    Uses values cached in the report -- no workbook re-read.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    for sheet in report.sheets:
        if sheet.classification == "empty":
            continue
        if sheet.classification == "computational" and not include_computational:
            continue

        values = report.values_by_sheet.get(sheet.name)
        if not values:
            continue

        if sheet.sub_tables:
            targets = sheet.sub_tables
        else:
            targets = [SubTable(
                top=1, left=1,
                bottom=sheet.n_rows, right=sheet.n_cols,
                header_rows=1,
                cell_count=sheet.n_rows * sheet.n_cols,
            )]

        for i, st in enumerate(targets, start=1):
            n_hdr = header_rows if header_rows is not None else st.header_rows

            sub_rows: list[list] = []
            for r in range(st.top - 1, st.bottom):
                if r >= len(values):
                    break
                row = values[r]
                slice_ = row[st.left - 1: st.right]
                if len(slice_) < (st.right - st.left + 1):
                    slice_ = list(slice_) + [None] * (
                        (st.right - st.left + 1) - len(slice_))
                sub_rows.append(slice_)

            if not sub_rows:
                continue

            if n_hdr >= 1 and len(sub_rows) > n_hdr:
                header = sub_rows[n_hdr - 1]
                seen: dict[str, int] = {}
                clean_header = []
                for j, h in enumerate(header):
                    base = "" if is_blank(h) else str(h)
                    if not base:
                        base = f"col_{j}"
                    if base in seen:
                        seen[base] += 1
                        base = f"{base}_{seen[base]}"
                    else:
                        seen[base] = 0
                    clean_header.append(base)
                df = pd.DataFrame(sub_rows[n_hdr:], columns=clean_header)
            else:
                df = pd.DataFrame(sub_rows)

            target = out_dir / f"{safe_name(sheet.name)}__t{i}_{st.excel_range()}.csv"
            df.to_csv(target, index=False)
            written.append(str(target))

    return written
