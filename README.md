# Pillar-Skills

Claude skills for Pillar Biosciences document-control workflows.

| Skill | What it does |
|---|---|
| [`label-spec-review`](label-spec-review/SKILL.md) | Reviews a label specification (LB-xxxx) to check that the symbols are correct, Section 2 and the label artwork agree in both directions, and the LB#/revision matches across the header, Section 2 and the artwork. Produces a findings report. |

## label-spec-review quick start

```bash
pip install python-docx
python3 label-spec-review/scripts/extract_label_doc.py LB-0669.docx --out review_out
```

Then ask Claude to "review the label spec". The skill reads `review_out/extract.json`, inspects
the exported artwork image, and writes a report like
[`examples/LB-0669-Rev1-review.md`](label-spec-review/examples/LB-0669-Rev1-review.md).
