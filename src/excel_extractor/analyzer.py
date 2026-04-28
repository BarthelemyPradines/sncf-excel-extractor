"""Top-level workbook analysis orchestrator."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .models import SubTable, SheetReport, WorkbookReport
from .scanner import scan_sheet_openpyxl, scan_sheet_calamine
from .detection import split_by_blank_lines, guess_header_rows, classify
from .media import extract_media, zip_metadata

try:
    from python_calamine import CalamineWorkbook  # type: ignore
    HAVE_CALAMINE = True
except ImportError:
    HAVE_CALAMINE = False


def analyze_workbook(xlsx_path: str | Path,
                     media_dir: str | Path | None = None,
                     prefer_calamine: bool = True) -> WorkbookReport:
    xlsx_path = Path(xlsx_path)
    meta = zip_metadata(xlsx_path)

    use_calamine = prefer_calamine and HAVE_CALAMINE
    cw = CalamineWorkbook.from_path(str(xlsx_path)) if use_calamine else None
    wb = (None if use_calamine
          else load_workbook(xlsx_path, read_only=True, data_only=True))

    sheet_names = cw.sheet_names if cw else wb.sheetnames

    sheet_reports: list[SheetReport] = []
    values_by_sheet: dict[str, list[list]] = {}

    for name in sheet_names:
        sheet_meta = meta.get(name, dict(n_merged=0, n_charts=0, n_images=0,
                                         has_listobjects=False))
        if cw:
            sig, mask, values = scan_sheet_calamine(cw, name)
        else:
            sig, mask, values = scan_sheet_openpyxl(wb[name])

        values_by_sheet[name] = values

        boxes = split_by_blank_lines(mask)
        single_region = len(boxes) <= 1

        sub_tables: list[SubTable] = []
        for r0, c0, r1, c1 in boxes:
            top, left, bottom, right = r0 + 1, c0 + 1, r1 + 1, c1 + 1
            cells = (bottom - top + 1) * (right - left + 1)
            if cells < 4:
                continue
            h = 1 if single_region else guess_header_rows(values, r0, c0, c1)
            sub_tables.append(SubTable(top, left, bottom, right, h, cells))

        cls, notes = classify(sig, sheet_meta, len(sub_tables))
        sheet_reports.append(SheetReport(
            name=name, classification=cls,
            n_rows=sig["n_rows"], n_cols=sig["n_cols"],
            n_filled=sig["n_filled"],
            n_formulas=sheet_meta["n_formulas"],
            n_cross_sheet_refs=sheet_meta["n_cross_sheet_refs"],
            n_merged=sheet_meta["n_merged"],
            n_charts=sheet_meta["n_charts"],
            n_images=sheet_meta["n_images"],
            has_listobjects=sheet_meta["has_listobjects"],
            sub_tables=sub_tables, notes=notes,
        ))

    if wb is not None:
        wb.close()

    if media_dir is None:
        media_dir = xlsx_path.with_suffix("").as_posix() + "_media"
    images, charts = extract_media(xlsx_path, media_dir)

    return WorkbookReport(
        path=str(xlsx_path),
        sheets=sheet_reports,
        extracted_media=images,
        extracted_charts=charts,
        values_by_sheet=values_by_sheet,
    )
