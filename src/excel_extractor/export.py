"""CSV export of detected sub-tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import SubTable, SheetReport, WorkbookReport, is_blank, safe_name


def _build_dataframe(values: list[list], st: SubTable,
                     header_rows: int | None = None) -> pd.DataFrame | None:
    """Build a DataFrame from cached values for one sub-table."""
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
        return None

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
        return pd.DataFrame(sub_rows[n_hdr:], columns=clean_header)
    else:
        return pd.DataFrame(sub_rows)


def _get_targets(sheet: SheetReport) -> list[SubTable]:
    """Return the sub-tables for a sheet, falling back to the whole sheet."""
    if sheet.sub_tables:
        return sheet.sub_tables
    return [SubTable(
        top=1, left=1,
        bottom=sheet.n_rows, right=sheet.n_cols,
        header_rows=1,
        cell_count=sheet.n_rows * sheet.n_cols,
    )]


def export_sheet_to_csv(sheet: SheetReport,
                        values: list[list],
                        out_dir: Path,
                        header_rows: int | None = None) -> list[str]:
    """Export one sheet's sub-tables as CSVs into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    for i, st in enumerate(_get_targets(sheet), start=1):
        df = _build_dataframe(values, st, header_rows)
        if df is None:
            continue
        target = out_dir / f"{safe_name(sheet.name)}__t{i}_{st.excel_range()}.csv"
        df.to_csv(target, index=False)
        written.append(str(target))

    return written


def export_sub_tables_to_csv(report: WorkbookReport,
                             out_dir: str | Path,
                             include_computational: bool = False,
                             header_rows: int | None = None) -> list[str]:
    """Write each detected sub-table to its own CSV (flat output, legacy API)."""
    out_dir = Path(out_dir)
    written: list[str] = []

    for sheet in report.sheets:
        if sheet.classification == "empty":
            continue
        if sheet.classification == "computational" and not include_computational:
            continue
        values = report.values_by_sheet.get(sheet.name)
        if not values:
            continue
        written.extend(export_sheet_to_csv(sheet, values, out_dir, header_rows))

    return written
