# Pillar-Skills

Claude skills for Pillar Biosciences document-control workflows.

| Skill | What it does |
|---|---|
| [`label-spec-review`](label-spec-review/SKILL.md) | Reviews a label specification (LB-xxxx) to check that the symbols are correct, Section 2 and the label artwork agree in both directions, and the LB#/revision matches across the header, Section 2 and the artwork. Produces a findings report. |
| [`revision-history-review`](revision-history-review/SKILL.md) | Reviews any controlled document (.docx/.pdf) for revision consistency: file name vs header, latest Rev in the revision history table vs header, revision history entries vs actual content, and, when an old version is attached, old-vs-new diff vs the revision history. Outputs a File / Discrepancy table. |

## label-spec-review quick start

```bash
pip install python-docx
python3 label-spec-review/scripts/extract_label_doc.py LB-0669.docx --out review_out
```

Then ask Claude to "review the label spec". The skill reads `review_out/extract.json`, inspects
the exported artwork image, and writes a report like
[`examples/LB-0669-Rev1-review.md`](label-spec-review/examples/LB-0669-Rev1-review.md).

## revision-history-review quick start

```bash
pip install python-docx pdfplumber
python3 revision-history-review/scripts/extract_doc.py "SOP-0012 Document Control Rev 3.docx" --out review_out
# optional, when the previous revision is available:
python3 revision-history-review/scripts/compare_versions.py "SOP-0012 Document Control Rev 2.docx" "SOP-0012 Document Control Rev 3.docx" --out review_out
```

Then ask Claude to "review the revision history". It produces a `File | Discrepancy` table like
[`examples/SOP-0012-Rev3-review.md`](revision-history-review/examples/SOP-0012-Rev3-review.md).
Files without a revision history table are reported as `no Rev. history Table of <file>`.
