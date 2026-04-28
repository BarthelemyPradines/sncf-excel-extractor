"""Sub-table detection, header-row guessing, and sheet classification."""

from __future__ import annotations

import numpy as np


def split_by_blank_lines(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    if mask.size == 0:
        return []
    boxes: list[tuple[int, int, int, int]] = []
    row_filled = mask.any(axis=1)

    row_groups: list[tuple[int, int]] = []
    i = 0
    while i < len(row_filled):
        if not row_filled[i]:
            i += 1
            continue
        j = i
        while j < len(row_filled) and row_filled[j]:
            j += 1
        row_groups.append((i, j - 1))
        i = j

    for r0, r1 in row_groups:
        sub = mask[r0:r1 + 1]
        col_filled = sub.any(axis=0)
        c = 0
        while c < len(col_filled):
            if not col_filled[c]:
                c += 1
                continue
            d = c
            while d < len(col_filled) and col_filled[d]:
                d += 1
            region = sub[:, c:d]
            rr = region.any(axis=1).nonzero()[0]
            cc = region.any(axis=0).nonzero()[0]
            if len(rr) and len(cc):
                boxes.append((
                    r0 + int(rr[0]), c + int(cc[0]),
                    r0 + int(rr[-1]), c + int(cc[-1]),
                ))
            c = d
    return boxes


def _cell_type(v) -> str | None:
    """Bucket a cell into a coarse type tag, or None if blank."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "b"
    if isinstance(v, (int, float)):
        return "n"
    if isinstance(v, str):
        return None if not v.strip() else "s"
    return "o"


def _row_signature(values: list[list], r: int,
                   left: int, right: int) -> tuple:
    if r >= len(values):
        return tuple([None] * (right - left + 1))
    row = values[r]
    return tuple(
        _cell_type(row[c]) if c < len(row) else None
        for c in range(left, right + 1)
    )


def _sigs_compatible(a: tuple, b: tuple, threshold: float = 0.7) -> bool:
    """Do two row signatures look like they belong to the same row-class?"""
    a_filled = sum(1 for x in a if x is not None)
    b_filled = sum(1 for x in b if x is not None)

    lo, hi = sorted((a_filled, b_filled))
    if lo <= 1 and hi > lo:
        return False
    if hi >= 3 and lo / hi < 0.5:
        return False

    matches = total = 0
    for x, y in zip(a, b):
        if x is None or y is None:
            continue
        total += 1
        if x == y:
            matches += 1
    return total > 0 and (matches / total) >= threshold


def guess_header_rows(values: list[list],
                      top: int, left: int, right: int,
                      max_check: int = 3) -> int:
    """Header rows have type signatures that differ from the row below them."""
    region_height = len(values) - top
    if region_height < 2:
        return 0

    end = min(top + max_check + 1, len(values))
    sigs = [_row_signature(values, r, left, right) for r in range(top, end)]
    if len(sigs) < 2:
        return 1

    for i in range(len(sigs) - 1):
        if _sigs_compatible(sigs[i], sigs[i + 1]):
            return max(i, 1) if i > 0 else 1
    return min(len(sigs) - 1, max_check)


def classify(sig: dict, meta: dict, n_subtables: int) -> tuple[str, list[str]]:
    notes: list[str] = []
    if sig["n_filled"] == 0:
        return "empty", ["sheet has no data"]
    if meta["n_charts"] or meta["n_images"]:
        notes.append(f"contains {meta['n_charts']} chart(s), "
                     f"{meta['n_images']} image(s)")
    if meta["n_cross_sheet_refs"] > 0:
        notes.append(f"{meta['n_cross_sheet_refs']} cross-sheet formula refs")
        return "computational", notes
    if meta["n_formulas"] > 0.05 * sig["n_filled"]:
        notes.append(f"formula-heavy ({meta['n_formulas']} formulas)")
        return "computational", notes
    if n_subtables > 1:
        return "multi_table", notes
    if meta["n_charts"] or meta["n_images"]:
        return "visual", notes
    return "trivial", notes
