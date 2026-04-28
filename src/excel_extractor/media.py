"""Zip-level metadata extraction, media extraction, and chart-to-sheet mapping."""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import NS, normalize_target

F_TAG_RE = re.compile(rb"<f(?:\s[^>]*)?>([^<]*)</f>")


def zip_metadata(xlsx_path: Path) -> dict:
    """Extract per-sheet metadata (formulas, merges, charts, images) from the xlsx zip."""
    sheets: dict[str, dict] = {}
    sheet_files: dict[str, str] = {}

    with zipfile.ZipFile(xlsx_path) as z:
        names = set(z.namelist())
        wb_xml = z.read("xl/workbook.xml")
        wb_rels = z.read("xl/_rels/workbook.xml.rels")
        rels = {r.attrib["Id"]: r.attrib["Target"]
                for r in ET.fromstring(wb_rels)}

        for s in ET.fromstring(wb_xml).findall("main:sheets/main:sheet", NS):
            name = s.attrib["name"]
            rid = s.attrib[f"{{{NS['r']}}}id"]
            target = rels[rid]
            sheet_files[name] = normalize_target(target)
            sheets[name] = dict(n_merged=0, n_charts=0, n_images=0,
                                n_formulas=0, n_cross_sheet_refs=0,
                                has_listobjects=False)

        for name, sheet_path in sheet_files.items():
            try:
                xml_bytes = z.read(sheet_path)
            except KeyError:
                continue
            sheets[name]["n_merged"] = xml_bytes.count(b"<mergeCell ")
            sheets[name]["has_listobjects"] = b"<tableParts" in xml_bytes

            formulas = F_TAG_RE.findall(xml_bytes)
            sheets[name]["n_formulas"] = len(formulas)
            sheets[name]["n_cross_sheet_refs"] = sum(
                1 for f in formulas if b"!" in f
            )

            rel_path = sheet_path.replace("worksheets/",
                                          "worksheets/_rels/") + ".rels"
            if rel_path in names:
                rel_xml = z.read(rel_path)
                drawing_targets = [
                    r.attrib["Target"]
                    for r in ET.fromstring(rel_xml)
                    if r.attrib.get("Type", "").endswith("/drawing")
                ]
                for dt in drawing_targets:
                    dt_norm = normalize_target(dt)
                    if dt_norm in names:
                        d_xml = z.read(dt_norm)
                        sheets[name]["n_charts"] += d_xml.count(b"<c:chart")
                        sheets[name]["n_images"] += d_xml.count(b"<xdr:pic")

    return sheets


def extract_media(xlsx_path: str | Path,
                  out_dir: str | Path) -> tuple[list[str], list[str]]:
    """Pull out embedded images and chart definitions from an .xlsx file."""
    xlsx_path = Path(xlsx_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images: list[str] = []
    charts: list[str] = []

    with zipfile.ZipFile(xlsx_path) as z:
        for name in z.namelist():
            base = Path(name).name
            if name.startswith("xl/media/"):
                target = out_dir / base
                with z.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                images.append(str(target))
            elif (name.startswith("xl/charts/")
                  and base.startswith("chart")
                  and base.endswith(".xml")):
                target = out_dir / base
                with z.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                charts.append(str(target))

    return images, charts


def chart_to_sheet_map(xlsx_path: str | Path) -> dict[str, list[str]]:
    """Map each sheet name to its chart XML basenames."""
    xlsx_path = Path(xlsx_path)
    out: dict[str, list[str]] = {}

    with zipfile.ZipFile(xlsx_path) as z:
        names = set(z.namelist())
        wb_xml = z.read("xl/workbook.xml")
        wb_rels = z.read("xl/_rels/workbook.xml.rels")
        rels = {r.attrib["Id"]: r.attrib["Target"]
                for r in ET.fromstring(wb_rels)}

        for s in ET.fromstring(wb_xml).findall("main:sheets/main:sheet", NS):
            sheet_name = s.attrib["name"]
            rid = s.attrib[f"{{{NS['r']}}}id"]
            sheet_path = normalize_target(rels[rid])
            out[sheet_name] = []

            sheet_rel_path = sheet_path.replace("worksheets/",
                                                "worksheets/_rels/") + ".rels"
            if sheet_rel_path not in names:
                continue
            sheet_rel_xml = z.read(sheet_rel_path)
            drawing_targets = [
                r.attrib["Target"]
                for r in ET.fromstring(sheet_rel_xml)
                if r.attrib.get("Type", "").endswith("/drawing")
            ]

            for dt in drawing_targets:
                dt_norm = normalize_target(dt)
                if dt_norm not in names:
                    continue
                drawing_rel_path = dt_norm.replace(
                    "drawings/", "drawings/_rels/") + ".rels"
                if drawing_rel_path not in names:
                    continue
                d_rel_xml = z.read(drawing_rel_path)
                for r in ET.fromstring(d_rel_xml):
                    t = r.attrib.get("Type", "")
                    if t.endswith("/chart"):
                        chart_target = normalize_target(r.attrib["Target"])
                        out[sheet_name].append(Path(chart_target).name)

    return out
