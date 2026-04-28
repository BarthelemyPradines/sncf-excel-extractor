"""Chart XML parsing and PNG rendering."""

from __future__ import annotations

import os
import re
from pathlib import Path
from xml.etree import ElementTree as ET

# Force Agg backend before anything imports pyplot.
os.environ.pop("MPLBACKEND", None)
import matplotlib
matplotlib.use("Agg", force=True)

from .models import safe_name
from .media import chart_to_sheet_map

CHART_NS = {
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}

REF_RE = re.compile(
    r"^(?:'([^']+)'|([^!]+))!"
    r"(\$?[A-Z]+)(\$?\d+)"
    r"(?::(\$?[A-Z]+)(\$?\d+))?$"
)


def _parse_ref(ref: str) -> tuple[str, int, int, int, int] | None:
    """Parse '<sheet>!<range>' into (sheet, r1, c1, r2, c2), 0-indexed."""
    from openpyxl.utils import column_index_from_string
    m = REF_RE.match(ref.strip())
    if not m:
        return None
    sheet = m.group(1) or m.group(2)
    c1 = column_index_from_string(m.group(3).lstrip("$")) - 1
    r1 = int(m.group(4).lstrip("$")) - 1
    if m.group(5):
        c2 = column_index_from_string(m.group(5).lstrip("$")) - 1
        r2 = int(m.group(6).lstrip("$")) - 1
    else:
        c2, r2 = c1, r1
    if r1 > r2:
        r1, r2 = r2, r1
    if c1 > c2:
        c1, c2 = c2, c1
    return sheet, r1, c1, r2, c2


def _resolve_ref(ref: str, values_by_sheet: dict[str, list[list]]) -> list:
    parsed = _parse_ref(ref)
    if not parsed:
        return []
    sheet, r1, c1, r2, c2 = parsed
    values = values_by_sheet.get(sheet, [])
    out: list = []
    for r in range(r1, r2 + 1):
        if r >= len(values):
            out.append(None)
            continue
        for c in range(c1, c2 + 1):
            out.append(values[r][c] if c < len(values[r]) else None)
    return out


def _chart_pts(elem: ET.Element,
               values_by_sheet: dict[str, list[list]] | None = None) -> list:
    if elem is None:
        return []
    pts = elem.findall(".//c:pt", CHART_NS)
    if pts:
        out = [None] * len(pts)
        for p in pts:
            idx = int(p.attrib.get("idx", "0"))
            v_node = p.find("c:v", CHART_NS)
            if v_node is None or v_node.text is None:
                continue
            v = v_node.text
            try:
                v = float(v)
            except ValueError:
                pass
            if idx < len(out):
                out[idx] = v
        return out

    if values_by_sheet is None:
        return []
    f_node = elem.find(".//c:f", CHART_NS)
    if f_node is None or f_node.text is None:
        return []
    return _resolve_ref(f_node.text, values_by_sheet)


def _chart_series(plot_elem: ET.Element,
                  values_by_sheet: dict[str, list[list]] | None = None) -> list[dict]:
    series = []
    for ser in plot_elem.findall("c:ser", CHART_NS):
        tx = ser.find("c:tx", CHART_NS)
        t_pts = _chart_pts(tx, values_by_sheet) if tx is not None else []
        title = (str(t_pts[0]) if t_pts and t_pts[0] is not None else None)

        cat = ser.find("c:cat", CHART_NS)
        cats = _chart_pts(cat, values_by_sheet) if cat is not None else []

        val = ser.find("c:val", CHART_NS)
        vals = _chart_pts(val, values_by_sheet) if val is not None else []

        xval = ser.find("c:xVal", CHART_NS)
        xs = (_chart_pts(xval, values_by_sheet)
              if xval is not None else None)

        yval = ser.find("c:yVal", CHART_NS)
        if yval is not None:
            vals = _chart_pts(yval, values_by_sheet)

        series.append(dict(title=title, categories=cats, values=vals, xs=xs))
    return series


def _render_one_chart(chart_xml_path: Path,
                      out_png: Path,
                      values_by_sheet: dict[str, list[list]] | None = None
                      ) -> bool:
    """Render a single chart XML to PNG. Returns True on success."""
    import matplotlib.pyplot as plt

    tree = ET.parse(chart_xml_path)
    root = tree.getroot()
    plot_area = root.find(".//c:plotArea", CHART_NS)
    if plot_area is None:
        return False

    title_parts = [t.text for t in root.findall(".//c:title//a:t", CHART_NS)
                   if t.text]
    title = "".join(title_parts) if title_parts else None

    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=120)
    rendered = False

    bar = plot_area.find("c:barChart", CHART_NS)
    if bar is not None:
        direction = bar.find("c:barDir", CHART_NS)
        horizontal = (direction is not None
                      and direction.attrib.get("val") == "bar")
        series = _chart_series(bar, values_by_sheet)
        if series and any(s["values"] for s in series):
            cats = series[0]["categories"] or list(
                range(len(series[0]["values"])))
            x = list(range(len(cats)))
            n = len(series)
            width = 0.8 / max(n, 1)
            for i, s in enumerate(series):
                offsets = [xx + (i - (n - 1) / 2) * width for xx in x]
                if horizontal:
                    ax.barh(offsets, s["values"], height=width,
                            label=s["title"])
                else:
                    ax.bar(offsets, s["values"], width=width,
                           label=s["title"])
            if horizontal:
                ax.set_yticks(x)
                ax.set_yticklabels([str(c) for c in cats])
            else:
                ax.set_xticks(x)
                ax.set_xticklabels([str(c) for c in cats], rotation=30,
                                   ha="right")
            rendered = True

    line = plot_area.find("c:lineChart", CHART_NS)
    if line is not None and not rendered:
        for s in _chart_series(line, values_by_sheet):
            if not s["values"]:
                continue
            cats = s["categories"] or list(range(len(s["values"])))
            ax.plot(range(len(cats)), s["values"], marker="o",
                    label=s["title"])
            ax.set_xticks(range(len(cats)))
            ax.set_xticklabels([str(c) for c in cats], rotation=30,
                               ha="right")
            rendered = True

    pie = plot_area.find("c:pieChart", CHART_NS)
    if pie is None:
        pie = plot_area.find("c:doughnutChart", CHART_NS)
    if pie is not None and not rendered:
        series = _chart_series(pie, values_by_sheet)
        if series and series[0]["values"]:
            s = series[0]
            pairs = [(c, v) for c, v in zip(s["categories"] or [],
                                            s["values"]) if v is not None]
            if pairs:
                cats, vals = zip(*pairs)
                ax.pie(vals, labels=[str(c) for c in cats],
                       autopct="%1.1f%%")
                ax.set_aspect("equal")
                rendered = True

    scatter = plot_area.find("c:scatterChart", CHART_NS)
    if scatter is not None and not rendered:
        for s in _chart_series(scatter, values_by_sheet):
            if not s["values"]:
                continue
            xs = s["xs"] if s["xs"] else list(range(len(s["values"])))
            ax.scatter(xs, s["values"], label=s["title"])
            rendered = True

    area = plot_area.find("c:areaChart", CHART_NS)
    if area is not None and not rendered:
        for s in _chart_series(area, values_by_sheet):
            if not s["values"]:
                continue
            cats = s["categories"] or list(range(len(s["values"])))
            ax.fill_between(range(len(cats)), s["values"], alpha=0.5,
                            label=s["title"])
            ax.plot(range(len(cats)), s["values"])
            ax.set_xticks(range(len(cats)))
            ax.set_xticklabels([str(c) for c in cats], rotation=30,
                               ha="right")
            rendered = True

    if not rendered:
        plt.close(fig)
        return False

    if title:
        ax.set_title(title)
    handles, labels = ax.get_legend_handles_labels()
    if any(labels):
        ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    return True


def render_charts_to_png(xlsx_path: str | Path,
                         chart_xml_paths: list[str],
                         out_dir: str | Path,
                         values_by_sheet: dict[str, list[list]] | None = None
                         ) -> list[str]:
    """Render each chart XML to a PNG."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    sheet_map = chart_to_sheet_map(xlsx_path)
    chart_to_sheet: dict[str, str] = {
        chart_name: sheet
        for sheet, chart_names in sheet_map.items()
        for chart_name in chart_names
    }

    seen_per_sheet: dict[str, int] = {}
    for chart_xml in chart_xml_paths:
        chart_xml = Path(chart_xml)
        sheet = chart_to_sheet.get(chart_xml.name, "unknown")
        seen_per_sheet[sheet] = seen_per_sheet.get(sheet, 0) + 1
        png_name = f"{safe_name(sheet)}__chart{seen_per_sheet[sheet]}.png"
        png_path = out_dir / png_name
        try:
            if _render_one_chart(chart_xml, png_path, values_by_sheet):
                written.append(str(png_path))
        except Exception as e:
            print(f"  warning: failed to render {chart_xml.name}: {e}")

    return written
