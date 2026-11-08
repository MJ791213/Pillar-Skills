---
name: label-spec-review
description: Review a Pillar Biosciences label specification document (LB-xxxx, e.g. "LB-0669 Fetal Antigen NIPT BOX 1 Label") for internal consistency before approval. Checks (1) symbols are correct ISO 15223-1:2021 symbols with correct meaning, (2) every item in Section 2 "Symbols and Information" appears on the label artwork (Figure 1), (3) everything on the artwork matches Section 2 (values, formats, no extra/unlisted content), and (4) the LB number and revision in the page header, in Section 2, and printed on the artwork all agree. Trigger on "review label", "label spec", "label review", "check label artwork", "LB-0", or when a label specification .docx/.pdf is uploaded.
---

# Label Specification Review

Purpose: replace the manual reviewer checklist for label specification documents
with a repeatable review that produces a findings report. The reviewer still signs
off; this skill does the line-by-line comparison.

## Document anatomy (what to expect)

| Part | Where | What it holds |
|---|---|---|
| Header | Every page | Logo, `LB-#### - <Title>`, `Rev. N`, `Page x of y` |
| Sec 1 Label Specifications | Body table | Part Number (e.g. MS-0191) |
| Sec 2 Symbols and Information | Body table, 3 rows | **Artwork**, **Symbols**, **Information** bullet lists |
| Sec 3 Label Artwork | Figure 1 image | The printable label (often printed twice, one copy rotated 180°) |

## Workflow

### Step 1 – Extract

For a `.docx`:

```bash
python3 <skill_dir>/scripts/extract_label_doc.py <file.docx> --out <scratch_dir>
```

This writes `<scratch_dir>/extract.json` (header text, Sec 1 and Sec 2 parsed into
lists, figure captions, automated pre-checks) and exports every embedded image to
`<scratch_dir>/images/`. Read `extract.json` first, then **open the artwork image(s)
with the Read tool** so you can inspect them visually. If the artwork is small or
blurry, crop/zoom with Pillow before reading.

For a `.pdf` (or screenshots): read the pages directly (Read tool with `pages`,
or the pdf skill) and build the same structure by hand: header, Sec 2 lists,
artwork.

The script's `auto_checks` cover the mechanical text-only comparisons (header vs
Sec 2 LB#/Rev, ISO citation formatting). Everything involving the artwork needs your
visual inspection – the artwork is an image, not text.

### Step 2 – Run the four checks

Work through every check. Do not skip an item because it "looks fine"; each
row of the report must cite what you saw.

**Check 1 – Symbols are correct and accurate**
For each entry in Sec 2 → Symbols:
- Look it up in `references/iso15223-1-2021-symbols.md`. Confirm the name is the
  standard's name, the cited standard is exactly `ISO 15223-1:2021`, and the
  citation format is consistent across the list (flag mixes like
  `ISO-15223-1-2021` vs `ISO-15223-1:2021`).
- Find the symbol on the artwork and confirm the graphic matches the standard
  (e.g. Manufacturer = filled factory; Date of manufacture = *outlined* factory;
  Use-by = hourglass; Batch code = `LOT` box; Catalogue number = `REF` box;
  Contains sufficient = Σ with n; Temperature limit = thermometer with both limits;
  Positive control = `CONTROL +` box; Caution = triangle with `!`).
- Confirm the data next to each symbol is the right kind of data (LOT next to the
  lot number, REF next to the catalogue number, hourglass next to the
  *expiration* date, not the manufacture date, etc.).
- Non-ISO symbols (e.g. **IUO**) must be listed without an ISO citation and be
  shown with their accompanying text ("Investigational Use Only").
- Flag any symbol on the artwork that is not listed in Sec 2.

**Check 2 – Every Sec 2 item is on the artwork (Sec 2 → artwork)**
Go through every bullet and sub-bullet in Artwork, Symbols and Information. For each,
record where it appears on Figure 1, or FAIL if it is missing. If the label is
printed twice (e.g. a rotated copy), check **both** copies.

**Check 3 – Artwork content matches Sec 2 (artwork → Sec 2)**
Go through every element on the artwork and confirm it is listed in Sec 2 with
identical text/value:
- Product name, kit/panel code, box `x of y`, REF, LOT placeholder, test count,
  temperature range and units, address, URL, phone, country of origin.
- Date formats: human-readable dates must match the stated format (e.g.
  `YYYY-MM-DD`). UDI/GS1 element strings use `(17)YYMMDD` / `(11)YYMMDD` with no
  separators. Flag the spec if it states `YY-MM-DD` for UDI but the artwork
  (correctly) prints `YYMMDD`, or the reverse.
- UDI human-readable AIs: (01) GTIN if used, (10) lot, (17) expiry, (11) mfg date.
  Confirm the AIs printed match the UDI Information list and the dates printed
  in the HRI are the same as the human-readable dates elsewhere on the label.
- Example/placeholder values (yellow "This is an Example" callouts) are
  acceptable but note them, and confirm the callouts sit outside the printable
  label area or are clearly annotations.
- Any text on the artwork not covered by Sec 2 = finding.

**Check 4 – LB number and revision agree everywhere**
Collect the LB#/Rev from: (a) the page header on every page, (b) the Sec 2
"Label part number and revision" item, (c) every copy printed on the artwork.
All must be identical (e.g. `LB-0669` / `Rev. 1`). Also confirm the header title
matches the document content (e.g. title says "BOX 1" and artwork says
"Box 1 of 4").

### Step 3 – Report

Write the report in this format (markdown; save it to a file if the user wants
a record):

```
# Label Review – <LB#> Rev <N> – <title>

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Symbols correct & accurate | PASS / FAIL / REVIEW | ... |
| 2 | Sec 2 items all on artwork | ... | ... |
| 3 | Artwork aligned with Sec 2 | ... | ... |
| 4 | LB# / Rev consistent | ... | header: ..., Sec 2: ..., artwork: ... |

## Item-by-item traceability
| Sec 2 item | Expected | On artwork (copy 1) | On artwork (copy 2) | Result |

## Findings
| Severity | Location | Finding | Suggested correction |
(Major = wrong/missing regulatory content; Minor = formatting/consistency;
 Observation = cosmetic or reviewer judgment)
```

Use **REVIEW** (not PASS) when the image is too low resolution to read a value
with confidence. Say so plainly; never guess at a value you cannot read.

## Notes

- `references/iso15223-1-2021-symbols.md` lists clause numbers from
  ISO 15223-1:2021. Compare it with the company's controlled copy of the standard
  before relying on it for a formal record.
- This skill reviews the specification for consistency. It does not replace
  regulatory assessment of which symbols are *required* for the product.
