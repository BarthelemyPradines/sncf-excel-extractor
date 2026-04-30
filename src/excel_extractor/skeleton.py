"""
Skeleton extraction for LLM-based multi-table detection.

Builds a compressed representation of a sheet that preserves structural
information (headers, separators, type transitions) while collapsing
repetitive data rows.

Approach
--------
1. **Row signature**: each row is reduced to a tuple of cell-type tags
   (TEXT, NUM, EMPTY, BOOL, DATE) plus a fill count. Two rows with
   identical signatures carry the same structural information.

2. **Deduplication**: consecutive runs of rows sharing the same signature
   are collapsed to just the first row. This removes hundreds of identical
   data rows while keeping one representative.

3. **Separator preservation**: empty or near-empty rows are always kept
   (they signal table boundaries).

4. **Transition preservation**: any row whose signature differs from the
   previous row is kept, even if it later repeats.

The result is a small DataFrame that retains every structural "event"
(header, type change, blank gap) but strips redundant data rows.
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Cell typing
# ---------------------------------------------------------------------------

def _cell_type_tag(value) -> str:
    """Classify a single cell value into a structural type tag."""
    if value is None:
        return "EMPTY"
    if isinstance(value, float) and pd.isna(value):
        return "EMPTY"
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, (int, float)):
        return "NUM"
    if isinstance(value, (datetime, date, time)):
        return "DATE"
    if isinstance(value, str):
        if not value.strip():
            return "EMPTY"
        # Try to detect numbers stored as strings
        stripped = value.strip().replace(",", "").replace(" ", "")
        try:
            float(stripped)
            return "NUM"
        except ValueError:
            pass
        # Detect percentage strings like "50.00%"
        if stripped.endswith("%"):
            try:
                float(stripped[:-1])
                return "NUM"
            except ValueError:
                pass
        return "TEXT"
    return "OTHER"


# ---------------------------------------------------------------------------
# Row signature
# ---------------------------------------------------------------------------

def compute_row_signature(row: pd.Series) -> tuple[tuple[str, ...], int]:
    """Compute a structural signature for one row.

    Returns
    -------
    (type_pattern, n_filled)
        type_pattern : tuple of cell-type tags, one per column
        n_filled     : number of non-empty cells
    """
    types: list[str] = []
    n_filled = 0
    for val in row:
        tag = _cell_type_tag(val)
        types.append(tag)
        if tag != "EMPTY":
            n_filled += 1
    return tuple(types), n_filled


def is_empty_row(sig: tuple[tuple[str, ...], int], threshold: int = 1) -> bool:
    """A row is considered empty/near-empty if it has <= threshold filled cells."""
    return sig[1] <= threshold


# ---------------------------------------------------------------------------
# Skeleton extraction
# ---------------------------------------------------------------------------

def extract_skeleton(df: pd.DataFrame) -> pd.DataFrame:
    """Compress a DataFrame into a structural skeleton.

    The skeleton keeps:
    - Every row where the type signature changes from the previous kept row
    - Every empty/near-empty row (table separators)
    - The first row of each run of identical signatures

    Consecutive data rows with the same signature are collapsed to one
    representative, dramatically reducing size while preserving layout.

    Parameters
    ----------
    df : pd.DataFrame
        Raw sheet data (as read from Excel, no preprocessing needed).

    Returns
    -------
    pd.DataFrame
        Skeleton with original index preserved (so row numbers map back
        to the source sheet).
    """
    if df.empty:
        return df.copy()

    # Compute signatures for every row
    signatures: list[tuple[tuple[str, ...], int]] = []
    for _, row in df.iterrows():
        signatures.append(compute_row_signature(row))

    # Walk through rows and decide which to keep
    keep_indices: list[int] = []
    prev_pattern: tuple[str, ...] | None = None

    for i, (pattern, n_filled) in enumerate(signatures):
        # Always keep empty/separator rows
        if is_empty_row(signatures[i]):
            keep_indices.append(i)
            prev_pattern = pattern
            continue

        # Keep if signature differs from the previous kept row
        if pattern != prev_pattern:
            keep_indices.append(i)
            prev_pattern = pattern
            continue

        # Same signature as previous kept row → skip (redundant data row)

    # Edge case: always include the very first and last non-empty rows
    # to anchor the sheet boundaries
    non_empty = [i for i, s in enumerate(signatures) if not is_empty_row(s)]
    if non_empty:
        if non_empty[0] not in keep_indices:
            keep_indices.append(non_empty[0])
        if non_empty[-1] not in keep_indices:
            keep_indices.append(non_empty[-1])

    keep_indices = sorted(set(keep_indices))
    return df.iloc[keep_indices].copy()


def extract_skeleton_from_excel(file_path: str, sheet_index: int) -> pd.DataFrame:
    """Read a sheet from an Excel file and return its skeleton.

    Parameters
    ----------
    file_path : str
        Path to the .xlsx file.
    sheet_index : int
        Zero-based sheet index.

    Returns
    -------
    pd.DataFrame
        Skeleton of the requested sheet.
    """
    df = pd.read_excel(
        file_path,
        sheet_name=sheet_index,
        header=None,       # don't interpret any row as header
        dtype=object,       # preserve raw types, no coercion
    )
    return extract_skeleton(df)
