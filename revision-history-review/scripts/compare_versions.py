#!/usr/bin/env python3
"""Compare an old and a new revision of a controlled document.

Usage:
    python3 compare_versions.py <old_file> <new_file> --out <dir>

Uses extract_doc.py to read both files (.docx, .pdf, .xlsx; the two files may be
different formats, e.g. old PDF vs new DOCX), then diffs the body section by
section, leaving out the revision history table itself. Same-format pairs are
compared paragraph/table-row by row; cross-format pairs sentence by sentence.
Writes <dir>/diff_<old>__<new>.json and .md, and prints the Rev numbers
found plus the revision history entries added since the old version. The
reviewer (Claude) then checks those entries against the actual changes.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_doc import extract, rev_key  # noqa: E402


REV_SECTION_WORDS = ("revision history", "rev. history", "rev history", "document history",
                     "change history", "revision record")


def linearize(data):
    """Body as a list of (section, text) lines, skipping the rev history table.
    Used when both files are the same format."""
    skip = (data.get("revision_history_table") or {}).get("table_index")
    lines, section = [], "(before first heading)"
    for b in data["body"]:
        if b["type"] == "heading":
            section = b["text"]
            lines.append((section, b["text"]))
        elif b["type"] == "para":
            lines.append((section, b["text"]))
        elif b["type"] == "table":
            if b["index"] == skip:
                continue
            for r in b["rows"]:
                lines.append((section, "[table] " + " | ".join(c for c in r)))
    return lines


def linearize_text(data):
    """Format-neutral version for cross-format pairs (e.g. old PDF vs new DOCX):
    joins each section's text (paragraphs and table cells) and splits it into
    sentences, so PDF line wrapping and table layout do not show as changes."""
    skip = (data.get("revision_history_table") or {}).get("table_index")
    pdf = data["file"].lower().endswith(".pdf")
    sections, order, section = {}, [], "(before first heading)"

    def push(sec, text):
        if sec not in sections:
            sections[sec] = []
            order.append(sec)
        sections[sec].append(text)

    for b in data["body"]:
        if b["type"] == "heading":
            section = b["text"]
            push(section, "")
        elif b["type"] == "para":
            push(section, b["text"])
        elif b["type"] == "table" and b["index"] != skip and not pdf:
            # PDF table text is already in the page text lines
            for r in b["rows"]:
                push(section, " ".join(c for c in r if c))
    lines = []
    for sec in order:
        if any(w in sec.lower() for w in REV_SECTION_WORDS):
            continue
        lines.append((sec, sec))
        text = re.sub(r"\s+", " ", " ".join(sections[sec])).strip()
        for sent in re.split(r"(?<=[.;:!?])\s+", text):
            if sent:
                lines.append((sec, sent))
    return lines


def diff(old, new, mode):
    lin = linearize if mode == "structured" else linearize_text
    a, b = lin(old), lin(new)
    sm = difflib.SequenceMatcher(a=[t for _, t in a], b=[t for _, t in b], autojunk=False)
    changes = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        old_lines = [t for _, t in a[i1:i2]]
        new_lines = [t for _, t in b[j1:j2]]
        section = (b[j1][0] if j1 < len(b) else a[i1][0]) if (j2 > j1) else (a[i1][0] if i1 < len(a) else "?")
        kind = {"replace": "modified", "delete": "deleted", "insert": "added"}[op]
        entry = {"type": kind, "section": section, "old": old_lines, "new": new_lines}
        if op == "replace" and len(old_lines) == len(new_lines):
            entry["word_diff"] = [word_diff(o, n) for o, n in zip(old_lines, new_lines)]
        changes.append(entry)
    return changes


def word_diff(o, n):
    ow, nw = o.split(), n.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ow, b=nw, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(" ".join(ow[i1:i2]))
        else:
            if i2 > i1:
                out.append("[-" + " ".join(ow[i1:i2]) + "-]")
            if j2 > j1:
                out.append("{+" + " ".join(nw[j1:j2]) + "+}")
    return " ".join(out)


def new_rev_entries(old, new):
    old_latest = old.get("latest_rev_in_table") or (old["header_summary"]["revs"] or [None])[-1]
    entries = new.get("revision_history") or []
    if not old_latest:
        return entries[-1:]
    return [e for e in entries if rev_key(e["rev"]) > rev_key(old_latest)]


def to_md(res):
    o, n = res["old"], res["new"]
    lines = [f"# Version comparison: {Path(o['file']).name} → {Path(n['file']).name}", "",
             "| | Old | New |", "|---|---|---|",
             f"| File name Rev | {o['file_name']['rev']} | {n['file_name']['rev']} |",
             f"| Header Rev | {', '.join(o['header_rev']) or '-'} | {', '.join(n['header_rev']) or '-'} |",
             f"| Latest Rev in table | {o['latest_rev_in_table']} | {n['latest_rev_in_table']} |", "",
             f"Comparison mode: **{res['mode']}**"
             + (" (files are different formats; compared sentence by sentence per section. "
                "Layout/table-structure differences are not shown; check tables by eye.)"
                if res["mode"] == "text" else ""), "",
             "## Revision history entries added in the new version", ""]
    if res["new_rev_entries"]:
        for e in res["new_rev_entries"]:
            lines.append(f"- **Rev {e['rev']}** ({e.get('date') or 'no date'}): {e['description']}")
    else:
        lines.append("- _(none found)_")
    lines += ["", f"## Body changes ({len(res['changes'])})", ""]
    for i, c in enumerate(res["changes"], 1):
        lines.append(f"### {i}. {c['type'].upper()} in {c['section']}")
        if c.get("word_diff"):
            lines += [f"- {w}" for w in c["word_diff"]]
        else:
            lines += [f"- OLD: {t}" for t in c["old"]] + [f"- NEW: {t}" for t in c["new"]]
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    old, new = extract(a.old), extract(a.new)
    if rev_key(new["file_name"]["rev"] or new["latest_rev_in_table"] or "") < rev_key(old["file_name"]["rev"] or old["latest_rev_in_table"] or ""):
        print("WARNING: the 'old' file has a higher Rev than the 'new' file; check the argument order.")
    same_format = Path(a.old).suffix.lower() == Path(a.new).suffix.lower()
    mode = "structured" if same_format else "text"
    res = {
        "mode": mode,
        "old": {"file": a.old, "file_name": old["file_name"], "header_rev": old["header_summary"]["revs"],
                "latest_rev_in_table": old["latest_rev_in_table"]},
        "new": {"file": a.new, "file_name": new["file_name"], "header_rev": new["header_summary"]["revs"],
                "latest_rev_in_table": new["latest_rev_in_table"]},
        "new_rev_entries": new_rev_entries(old, new),
        "changes": diff(old, new, mode),
    }
    stem = f"diff_{Path(a.old).stem}__{Path(a.new).stem}"
    (out / f"{stem}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    (out / f"{stem}.md").write_text(to_md(res))
    print(f"old: file Rev {res['old']['file_name']['rev']}, header {res['old']['header_rev']}, table latest {res['old']['latest_rev_in_table']}")
    print(f"new: file Rev {res['new']['file_name']['rev']}, header {res['new']['header_rev']}, table latest {res['new']['latest_rev_in_table']}")
    print(f"rev history entries added: {[e['rev'] for e in res['new_rev_entries']]}")
    print(f"comparison mode: {mode}")
    print(f"body changes: {len(res['changes'])}")
    print(f"-> {out / (stem + '.md')}")


if __name__ == "__main__":
    main()
