#!/usr/bin/env python3
"""Extract file name, page header, revision history table and body text from
controlled documents, and run the mechanical revision checks.

Usage:
    python3 extract_doc.py <file> [<file> ...] --out <dir>

Supports .docx (python-docx) and .pdf (pdfplumber, falls back to pdftotext).
For each input writes <dir>/<stem>.json and prints a one-line summary of
each automated check. Content checks (does the body reflect what the revision
history says changed?) need reading and judgment, so they are left to the
reviewer / Claude; this script gives them the structured material to do it.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DOCNUM_RE = re.compile(r"\b([A-Z]{1,6}-\d{2,6}(?:-\d{1,4})?)\b")
REV_RE = re.compile(r"\bRev(?:ision)?\.?[\s_#:-]*([A-Z]{1,2}\d*|\d+(?:\.\d+)?)\b", re.I)
REV_HEADER_RE = re.compile(r"^\s*(rev(ision)?\.?\s*(#|no\.?|number|level)?|version|ver\.?)\s*$", re.I)
REV_TABLE_KEYWORDS = ("revision history", "rev. history", "rev history", "document history",
                      "change history", "revision record", "history of changes")
DESC_HEADER_RE = re.compile(r"(description|change|summary|reason|update|detail)", re.I)
DATE_HEADER_RE = re.compile(r"(date|effective)", re.I)
SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def norm_title(s):
    s = (s or "").lower()
    s = re.sub(r"[_\-–—.,()]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def rev_key(rev):
    """Sort key that handles 1, 01, 2.1, A, B, AA, A1."""
    r = (rev or "").strip().upper()
    if re.fullmatch(r"\d+(\.\d+)?", r):
        return (0, tuple(int(x) for x in r.split(".")), "")
    m = re.fullmatch(r"([A-Z]+)(\d*)", r)
    if m:
        letters = 0
        for ch in m.group(1):
            letters = letters * 26 + (ord(ch) - 64)
        return (1, (letters, int(m.group(2) or 0)), "")
    return (2, (), r)


def canon_rev(rev):
    r = (rev or "").strip().upper()
    if re.fullmatch(r"\d+", r):
        return str(int(r))  # "01" == "1"
    return r


def parse_filename(path):
    stem = Path(path).stem
    spaced = re.sub(r"[_]+", " ", stem)
    doc = DOCNUM_RE.search(spaced.upper())
    rev = REV_RE.search(spaced)
    title = spaced
    for m in (rev, doc):
        if m:
            title = title.replace(m.group(0), " ") if m is rev else re.sub(re.escape(m.group(1)), " ", title, flags=re.I)
    title = norm(re.sub(r"^[\s\-–—]+|[\s\-–—]+$", "", norm(title)))
    return {
        "stem": stem,
        "doc_number": doc.group(1) if doc else None,
        "rev": canon_rev(rev.group(1)) if rev else None,
        "title": title or None,
    }


def parse_header(text):
    t = norm(text)
    doc = DOCNUM_RE.search(t)
    revs = sorted({canon_rev(m) for m in REV_RE.findall(t)}, key=rev_key)
    title = t
    title = re.sub(r"Page\s*\d+\s*(of\s*\d+)?", " ", title, flags=re.I)
    title = REV_RE.sub(" ", title)
    if doc:
        title = title.replace(doc.group(1), " ")
    title = re.sub(r"\b(effective date|doc(ument)?\s*(no\.?|number|#)|title)\s*:?", " ", title, flags=re.I)
    title = norm(re.sub(r"\s*[|]\s*", " ", title)).strip(" -–—:")
    return {"doc_number": doc.group(1) if doc else None, "revs": revs, "title": title or None}


# --------------------------------------------------------------------------
# revision history table detection
# --------------------------------------------------------------------------
def find_rev_table(tables, context_before):
    """tables: list of row-lists (list of cell strings). context_before: text
    preceding each table (heading). Returns (index, header_row_idx, col_map)."""
    best = None
    for ti, rows in enumerate(tables):
        for hi, row in enumerate(rows):
            cells = [norm(c) for c in row]
            rev_col = next((i for i, c in enumerate(cells) if REV_HEADER_RE.match(c)), None)
            if rev_col is None:
                continue
            desc_col = next((i for i, c in enumerate(cells) if i != rev_col and DESC_HEADER_RE.search(c)), None)
            date_col = next((i for i, c in enumerate(cells) if i not in (rev_col, desc_col) and DATE_HEADER_RE.search(c)), None)
            score = 2 + (desc_col is not None) * 2 + (date_col is not None)
            if any(k in (context_before[ti] or "").lower() for k in REV_TABLE_KEYWORDS):
                score += 3
            if best is None or score >= best[0]:  # >= : prefer the later table (usually last section)
                best = (score, ti, hi, {"rev": rev_col, "description": desc_col, "date": date_col, "headers": cells})
            break  # first matching row is the header row of this table
    if best and best[0] >= 4:
        return best[1:]
    return None


def build_rev_history(rows, hi, cols):
    entries = []
    for row in rows[hi + 1:]:
        cells = [norm(c) for c in row]
        if not any(cells):
            continue
        rev = cells[cols["rev"]] if cols["rev"] < len(cells) else ""
        rev = re.sub(r"^rev(ision)?\.?\s*", "", rev, flags=re.I).strip()
        if not rev:  # wrapped header text, or continuation of the previous description
            if entries and cols["description"] is not None and cols["description"] < len(cells):
                entries[-1]["description"] = norm(entries[-1]["description"] + " " + cells[cols["description"]])
            continue
        entries.append({
            "rev": canon_rev(rev),
            "date": cells[cols["date"]] if cols["date"] is not None and cols["date"] < len(cells) else None,
            "description": cells[cols["description"]] if cols["description"] is not None and cols["description"] < len(cells) else " | ".join(cells),
            "row": cells,
        })
    return entries


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------
def extract_docx(path):
    try:
        import docx
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        sys.exit("python-docx is required: pip install python-docx")

    d = docx.Document(path)

    def blocks(parent_elm, parent):
        for child in parent_elm.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, parent)
            elif child.tag == qn("w:tbl"):
                yield Table(child, parent)
            elif child.tag == qn("w:sdt"):  # content controls wrap paragraphs/tables
                content = child.find(qn("w:sdtContent"))
                if content is not None:
                    yield from blocks(content, parent)

    def table_rows(tbl):
        out = []
        for row in tbl.rows:
            seen, cells = set(), []
            for c in row.cells:
                if id(c._tc) in seen:
                    continue
                seen.add(id(c._tc))
                cells.append(c.text)
            out.append(cells)
        return out

    def container_text(part):
        lines = []
        for b in blocks(part._element, part):
            if isinstance(b, Paragraph):
                lines.append(b.text)
            else:
                for r in table_rows(b):
                    lines.append(" | ".join(norm(c) for c in r))
        return "\n".join(l for l in lines if l.strip())

    headers = []
    for i, sec in enumerate(d.sections):
        for kind, hdr in (("default", sec.header), ("first_page", sec.first_page_header),
                          ("even_page", sec.even_page_header)):
            if i > 0 and hdr.is_linked_to_previous:
                continue
            t = container_text(hdr)
            if t.strip():
                headers.append({"section": i, "type": kind, "text": t})

    body, tables, ctx, last_heading = [], [], [], None
    for b in blocks(d.element.body, d):
        if isinstance(b, Paragraph):
            text = norm(b.text)
            if not text:
                continue
            style = (b.style.name if b.style is not None else "") or ""
            is_heading = style.lower().startswith("heading") or style.lower() == "title"
            num = None
            m = SECTION_RE.match(text)
            if m and (is_heading or len(text) < 90):
                num = m.group(1)
            if is_heading or num:
                last_heading = text
            body.append({"type": "heading" if (is_heading or num) else "para", "style": style, "text": text})
        else:
            rows = table_rows(b)
            tables.append(rows)
            ctx.append(last_heading)
            body.append({"type": "table", "index": len(tables) - 1, "under": last_heading,
                         "rows": [[norm(c) for c in r] for r in rows]})

    props = d.core_properties
    meta = {"title": props.title, "subject": props.subject, "revision": props.revision}
    return headers, body, tables, ctx, meta


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def extract_pdf(path):
    headers, body, tables, ctx = [], [], [], []
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None

    if pdfplumber:
        with pdfplumber.open(path) as pdf:
            last_heading = None
            for pno, page in enumerate(pdf.pages):
                h = page.height
                top = page.crop((0, 0, page.width, h * 0.12)).extract_text() or ""
                if top.strip():
                    headers.append({"section": pno, "type": f"page {pno + 1} top band", "text": top})
                text = page.crop((0, h * 0.12, page.width, h * 0.94)).extract_text() or ""
                for line in text.splitlines():
                    line = norm(line)
                    if not line:
                        continue
                    if SECTION_RE.match(line) and len(line) < 90:
                        last_heading = line
                        body.append({"type": "heading", "page": pno + 1, "text": line})
                    else:
                        body.append({"type": "para", "page": pno + 1, "text": line})
                page_tables = page.extract_tables()
                if not page_tables and any(k in text.lower() for k in REV_TABLE_KEYWORDS):
                    # borderless table: fall back to text-alignment detection
                    body_area = page.crop((0, h * 0.12, page.width, h * 0.94))
                    page_tables = body_area.extract_tables({"vertical_strategy": "text",
                                                            "horizontal_strategy": "text"})
                for t in page_tables:
                    rows = [[c or "" for c in r] for r in t]
                    tables.append(rows)
                    ctx.append(last_heading)
                    body.append({"type": "table", "index": len(tables) - 1, "page": pno + 1,
                                 "under": last_heading, "rows": [[norm(c) for c in r] for r in rows]})
    else:
        out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout
        for pno, page in enumerate(out.split("\f")):
            lines = [l for l in page.splitlines() if l.strip()]
            if lines:
                headers.append({"section": pno, "type": f"page {pno + 1} first lines", "text": "\n".join(lines[:3])})
            for l in lines[3:]:
                body.append({"type": "para", "page": pno + 1, "text": norm(l)})
    return headers, body, tables, ctx, {}


def extract_text(path):
    lines = [norm(l) for l in Path(path).read_text(errors="replace").splitlines()]
    headers = [{"section": 0, "type": "first lines", "text": "\n".join(l for l in lines[:3] if l)}]
    body = [{"type": "para", "text": l} for l in lines[3:] if l]
    return headers, body, [], [], {}


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------
def run_checks(fn, hdr, rev_hist, rev_table):
    checks = []

    def add(cid, name, result, **kw):
        checks.append({"id": cid, "check": name, "result": result, **kw})

    # 1. file name vs header -------------------------------------------------
    if fn["doc_number"] and hdr["doc_number"]:
        add("1a", "File name doc # vs header doc #",
            "PASS" if fn["doc_number"].upper() == hdr["doc_number"].upper() else "FAIL",
            file_name=fn["doc_number"], header=hdr["doc_number"])
    else:
        add("1a", "File name doc # vs header doc #", "REVIEW",
            file_name=fn["doc_number"], header=hdr["doc_number"],
            note="Doc # not found in file name and/or header; compare manually.")

    if fn["rev"] and hdr["revs"]:
        add("1b", "File name Rev vs header Rev",
            "PASS" if hdr["revs"] == [fn["rev"]] else "FAIL", file_name=fn["rev"], header=hdr["revs"])
    else:
        add("1b", "File name Rev vs header Rev", "REVIEW" if hdr["revs"] else "FAIL",
            file_name=fn["rev"], header=hdr["revs"],
            note="Rev missing from file name" if hdr["revs"] else "Rev not found in header")
    if len(hdr["revs"]) > 1:
        add("1c", "Header Rev consistent on all pages/sections", "FAIL", header=hdr["revs"])

    ft, ht = norm_title(fn["title"]), norm_title(hdr["title"])
    if ft and ht:
        ok = ft == ht or ft in ht or ht in ft
        add("1d", "File name title vs header title", "PASS" if ok else "REVIEW",
            file_name=fn["title"], header=hdr["title"],
            note=None if ok else "Titles differ in wording; judge whether this is a real mismatch.")
    else:
        add("1d", "File name title vs header title", "REVIEW", file_name=fn["title"], header=hdr["title"])

    # 2 / 4. revision history table -----------------------------------------
    if rev_table is None:
        add("4", "Revision history table present", "FAIL", note="no Rev. history Table")
        return checks
    if rev_table.get("table_index") is None:
        add("4", "Revision history table present", "REVIEW",
            note="Revision history heading found but no parsable table; read it manually.")
        return checks
    add("4", "Revision history table present", "PASS", entries=len(rev_hist))
    if not rev_hist:
        add("2a", "Latest Rev in table vs header Rev", "FAIL", note="Revision history table has no entries")
        return checks

    revs = [e["rev"] for e in rev_hist]
    last, highest = revs[-1], max(revs, key=rev_key)
    latest = highest
    header_rev = hdr["revs"][0] if len(hdr["revs"]) == 1 else None
    add("2a", "Latest Rev in table vs header Rev",
        "PASS" if header_rev and canon_rev(latest) == header_rev else "FAIL",
        table_latest=latest, header=hdr["revs"])
    if fn["rev"]:
        add("2b", "Latest Rev in table vs file name Rev",
            "PASS" if canon_rev(latest) == fn["rev"] else "FAIL", table_latest=latest, file_name=fn["rev"])
    if last != highest and revs[0] != highest:
        add("2c", "Table rows in Rev order", "REVIEW", order=revs,
            note="Highest Rev is neither the last nor first row; check table order.")
    dups = sorted({r for r in revs if revs.count(r) > 1})
    if dups:
        add("2d", "Duplicate Rev entries", "FAIL", duplicates=dups)
    numeric = [r for r in revs if re.fullmatch(r"\d+", r)]
    if len(numeric) == len(revs) and len(revs) > 1:
        ordered = sorted(int(r) for r in revs)
        gaps = [n for n in range(ordered[0], ordered[-1] + 1) if n not in ordered]
        if gaps:
            add("2e", "Skipped Rev numbers", "REVIEW", missing=[str(g) for g in gaps])
    latest_entry = next(e for e in reversed(rev_hist) if e["rev"] == latest)
    if not norm(latest_entry["description"]):
        add("3a", "Latest Rev has a change description", "FAIL")
    return checks


def extract(path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".docx":
        headers, body, tables, ctx, meta = extract_docx(path)
    elif ext == ".pdf":
        headers, body, tables, ctx, meta = extract_pdf(path)
    elif ext in (".txt", ".md"):
        headers, body, tables, ctx, meta = extract_text(path)
    else:
        sys.exit(f"Unsupported file type: {path.name} (convert .doc to .docx first)")

    fn = parse_filename(path)
    hdr = parse_header("\n".join(h["text"] for h in headers))
    # per-header-instance revs, so a mismatch on one page is visible
    per_header = [{**h, "parsed": parse_header(h["text"])} for h in headers]

    found = find_rev_table(tables, ctx)
    rev_hist, rev_table = [], None
    if found:
        ti, hi, cols = found
        rev_hist = build_rev_history(tables[ti], hi, cols)
        rev_table = {"table_index": ti, "under_heading": ctx[ti], "columns": cols["headers"]}
    else:
        # text-only fallback: look for a "Revision History" heading in the body
        idx = next((i for i, b in enumerate(body) if b["type"] != "table"
                    and any(k in b["text"].lower() for k in REV_TABLE_KEYWORDS)), None)
        if idx is not None:
            rev_table = {"table_index": None, "under_heading": body[idx]["text"],
                         "note": "Heading found but no parsable table; read the section manually.",
                         "following_text": [b.get("text") for b in body[idx + 1: idx + 25]]}

    latest = max((e["rev"] for e in rev_hist), key=rev_key) if rev_hist else None
    return {
        "file": str(path),
        "file_name": fn,
        "headers": per_header,
        "header_summary": hdr,
        "metadata": meta,
        "revision_history_table": rev_table,
        "revision_history": rev_hist,
        "latest_rev_in_table": latest,
        "latest_change_description": next((e["description"] for e in reversed(rev_hist) if e["rev"] == latest), None),
        "auto_checks": run_checks(fn, hdr, rev_hist, rev_table),
        "body": body,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in a.files:
        data = extract(f)
        dest = out / f"{Path(f).stem}.json"
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"== {Path(f).name}")
        h = data["header_summary"]
        print(f"   file name : doc={data['file_name']['doc_number']} rev={data['file_name']['rev']} title={data['file_name']['title']!r}")
        print(f"   header    : doc={h['doc_number']} rev={h['revs']} title={h['title']!r}")
        print(f"   rev table : latest={data['latest_rev_in_table']} entries={len(data['revision_history'])}")
        for c in data["auto_checks"]:
            extra = c.get("note") or ""
            print(f"   [{c['result']:6}] {c['id']:3} {c['check']} {extra}")
        print(f"   -> {dest}")


if __name__ == "__main__":
    main()
