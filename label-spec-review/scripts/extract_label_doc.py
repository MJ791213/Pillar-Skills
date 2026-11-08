#!/usr/bin/env python3
"""Extract the reviewable content of a label specification .docx.

Usage:
    python3 extract_label_doc.py <label_spec.docx> --out <dir>

Writes <dir>/extract.json and exports embedded images to <dir>/images/.
The artwork itself is an image, so artwork checks are left to visual review;
this script handles header / Section 1 / Section 2 parsing and the mechanical
text-only checks (LB#/Rev consistency, ISO citation formatting).
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import docx
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except ImportError:
    sys.exit("python-docx is required: pip install python-docx")

LB_RE = re.compile(r"\bLB-\d{3,5}\b", re.I)
REV_RE = re.compile(r"\bRev(?:ision)?\.?\s*(\d+[A-Z]?|[A-Z])\b", re.I)
ISO_RE = re.compile(r"ISO[\s-]*15223[\s-]*1[\s:-]*(\d{4})?", re.I)
ISO_CANONICAL = "ISO 15223-1:2021"


def iter_block_items(parent):
    """Yield paragraphs and tables of a body/cell/header in document order."""
    elm = parent.element.body if hasattr(parent, "element") and hasattr(parent.element, "body") else parent._element
    for child in elm.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def para_level(p):
    """List nesting level of a paragraph (0 = top bullet, 1 = sub-bullet ...)."""
    ppr = p._p.pPr
    if ppr is not None and ppr.numPr is not None and ppr.numPr.ilvl is not None:
        return int(ppr.numPr.ilvl.val)
    m = re.search(r"(\d+)$", p.style.name or "") if p.style is not None else None
    if m and "list" in (p.style.name or "").lower():
        return int(m.group(1)) - 1
    indent = p.paragraph_format.left_indent
    if indent is not None and indent.pt > 54:
        return 1
    return 0


def cell_items(cell):
    """Return a cell's paragraphs as a nested list structure."""
    items = []
    for p in cell.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        lvl = para_level(p)
        if lvl > 0 and items:
            items[-1].setdefault("sub", []).append(text)
        else:
            items.append({"text": text})
    return items


def table_rows(tbl):
    rows = []
    for row in tbl.rows:
        cells, seen = [], set()
        for c in row.cells:  # merged cells repeat; de-duplicate
            if id(c._tc) in seen:
                continue
            seen.add(id(c._tc))
            cells.append(c)
        rows.append(cells)
    return rows


def text_of(container):
    parts = []
    for block in iter_block_items(container):
        if isinstance(block, Paragraph):
            parts.append(block.text)
        else:
            for row in table_rows(block):
                parts.append(" | ".join(c.text.strip() for c in row))
    return "\n".join(t for t in parts if t.strip())


def image_rids(element):
    return [b.get(qn("r:embed")) for b in element.iter(qn("a:blip")) if b.get(qn("r:embed"))]


def export_image(part_rels, rid, out_dir, name):
    rel = part_rels.get(rid)
    if rel is None or rel.is_external:
        return None
    blob = rel.target_part.blob
    ext = Path(rel.target_part.partname).suffix or ".bin"
    path = out_dir / f"{name}{ext}"
    path.write_bytes(blob)
    return str(path)


def extract(path, out):
    d = docx.Document(path)
    img_dir = out / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # ---- headers -------------------------------------------------------
    headers = []
    for i, sec in enumerate(d.sections):
        for kind, hdr in (("default", sec.header), ("first_page", sec.first_page_header), ("even_page", sec.even_page_header)):
            if hdr.is_linked_to_previous and i > 0:
                continue
            t = text_of(hdr)
            if t.strip():
                headers.append({"section": i, "type": kind, "text": t})

    # ---- body ------------------------------------------------------------
    body_blocks, sections, figures, images = [], {}, [], []
    current_heading, img_n, last_image = None, 0, None
    for block in iter_block_items(d):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            style = block.style.name if block.style is not None else ""
            for rid in image_rids(block._p):
                img_n += 1
                p = export_image(d.part.rels, rid, img_dir, f"body_{img_n:02d}")
                if p:
                    last_image = {"file": p, "after_heading": current_heading}
                    images.append(last_image)
            if not text:
                continue
            if style.lower().startswith("heading") or re.match(r"^\d+\s+[A-Z]", text):
                current_heading = text
                body_blocks.append({"heading": text})
            elif re.match(r"^(Figure|Fig\.?)\s*\d+", text, re.I):
                figures.append({"caption": text, "image": last_image["file"] if last_image else None})
                body_blocks.append({"caption": text})
            else:
                body_blocks.append({"text": text})
        else:
            for rid in image_rids(block._tbl):
                img_n += 1
                p = export_image(d.part.rels, rid, img_dir, f"body_{img_n:02d}")
                if p:
                    last_image = {"file": p, "after_heading": current_heading}
                    images.append(last_image)
            parsed = {}
            for row in table_rows(block):
                if len(row) >= 2:
                    key = row[0].text.strip().rstrip(":")
                    parsed[key] = cell_items(row[1]) if len(row[1].paragraphs) > 1 else row[1].text.strip()
            sections.setdefault(current_heading or "(no heading)", []).append(parsed)
            body_blocks.append({"table_under": current_heading, "rows": parsed})

    # images in headers (logos) – exported for completeness
    for i, sec in enumerate(d.sections):
        for rid in image_rids(sec.header._element):
            p = export_image(sec.header.part.rels, rid, img_dir, f"header_s{i}_{rid}")
            if p:
                images.append({"file": p, "after_heading": "(page header)"})

    sec2 = next((v[0] for k, v in sections.items() if "symbol" in k.lower()), {})
    sec1 = next((v[0] for k, v in sections.items() if "specification" in k.lower()), {})

    return {
        "file": str(path),
        "headers": headers,
        "section1": sec1,
        "section2": sec2,
        "figures": figures,
        "images": images,
        "body": body_blocks,
        "auto_checks": auto_checks(headers, sec2),
    }


def flatten(items):
    out = []
    for it in items if isinstance(items, list) else [{"text": items}]:
        out.append(it["text"])
        out.extend(it.get("sub", []))
    return out


def auto_checks(headers, sec2):
    checks = []
    header_text = "\n".join(h["text"] for h in headers)
    h_lb = sorted(set(m.upper() for m in LB_RE.findall(header_text)))
    h_rev = sorted(set(m.upper() for m in REV_RE.findall(header_text)))

    info = flatten(sec2.get("Information", []))
    pn_lines = []
    for i, line in enumerate(info):
        if "part number and revision" in line.lower():
            pn_lines = info[i:i + 3]
    pn_text = " ".join(pn_lines) or " ".join(info)
    s_lb = sorted(set(m.upper() for m in LB_RE.findall(pn_text)))
    s_rev = sorted(set(m.upper() for m in REV_RE.findall(pn_text)))

    checks.append({
        "check": "4a LB# header vs Sec 2",
        "header": h_lb, "section2": s_lb,
        "result": "PASS" if h_lb and h_lb == s_lb and len(h_lb) == 1 else "FAIL",
    })
    checks.append({
        "check": "4b Rev header vs Sec 2",
        "header": h_rev, "section2": s_rev,
        "result": "PASS" if h_rev and h_rev == s_rev and len(h_rev) == 1 else "FAIL",
    })
    checks.append({
        "check": "4c LB#/Rev printed on artwork",
        "result": "VISUAL",
        "note": f"Confirm every copy on the artwork reads {', '.join(h_lb) or '?'} Rev. {', '.join(h_rev) or '?'}",
    })

    symbols = flatten(sec2.get("Symbols", []))
    bad = []
    for s in symbols:
        for m in ISO_RE.finditer(s):
            if m.group(0) != ISO_CANONICAL:
                bad.append({"item": s, "citation": m.group(0), "expected": ISO_CANONICAL})
    styles = sorted(set(m.group(0) for s in symbols for m in ISO_RE.finditer(s)))
    checks.append({
        "check": "1a ISO citation format",
        "result": "PASS" if not bad else "FAIL",
        "citation_variants_found": styles,
        "nonconforming": bad,
    })
    checks.append({
        "check": "2/3 Sec 2 checklist for artwork comparison",
        "result": "VISUAL",
        "artwork_items": flatten(sec2.get("Artwork", [])),
        "symbol_items": symbols,
        "information_items": info,
    })
    return checks


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("docx")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = extract(Path(a.docx), out)
    (out / "extract.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    for c in data["auto_checks"]:
        print(f"[{c['result']:6}] {c['check']}")
    print(f"images: {len(data['images'])} -> {out / 'images'}")
    print(f"wrote {out / 'extract.json'}")


if __name__ == "__main__":
    main()
