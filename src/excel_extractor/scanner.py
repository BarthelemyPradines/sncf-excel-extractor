"""Single-pass sheet scanning (openpyxl and calamine backends)."""

from __future__ import annotations

import numpy as np

from .models import is_blank


def scan_sheet_openpyxl(ws) -> tuple[dict, np.ndarray, list[list]]:
    """Single pass: count filled cells and build mask + cached values."""
    n_filled = 0
    values: list[list] = []
    last_nonempty = -1

    for ri, row in enumerate(ws.iter_rows(values_only=True)):
        row_list = list(row)
        values.append(row_list)
        any_filled = False
        for v in row_list:
            if is_blank(v):
                continue
            n_filled += 1
            any_filled = True
        if any_filled:
            last_nonempty = ri

    if last_nonempty < 0:
        return (dict(n_rows=0, n_cols=0, n_filled=0),
                np.zeros((0, 0), dtype=bool), [])

    values = values[: last_nonempty + 1]
    max_c = max((len(r) for r in values), default=0)
    mask = np.zeros((len(values), max_c), dtype=bool)
    for ri, row in enumerate(values):
        for ci, v in enumerate(row):
            if not is_blank(v):
                mask[ri, ci] = True

    sig = dict(n_rows=len(values), n_cols=max_c, n_filled=n_filled)
    return sig, mask, values


def scan_sheet_calamine(cw, sheet_name: str) -> tuple[dict, np.ndarray, list[list]]:
    sheet = cw.get_sheet_by_name(sheet_name)
    rows = sheet.to_python(skip_empty_area=False)
    if not rows:
        return (dict(n_rows=0, n_cols=0, n_filled=0),
                np.zeros((0, 0), dtype=bool), [])

    n_filled = 0
    last_r = -1
    for ri, row in enumerate(rows):
        for v in row:
            if is_blank(v):
                continue
            n_filled += 1
            last_r = ri

    if last_r < 0:
        return (dict(n_rows=0, n_cols=0, n_filled=0),
                np.zeros((0, 0), dtype=bool), [])

    values = [list(r) for r in rows[: last_r + 1]]
    max_c = max((len(r) for r in values), default=0)
    mask = np.zeros((len(values), max_c), dtype=bool)
    for ri, row in enumerate(values):
        for ci, v in enumerate(row):
            if not is_blank(v):
                mask[ri, ci] = True

    sig = dict(n_rows=len(values), n_cols=max_c, n_filled=n_filled)
    return sig, mask, values
