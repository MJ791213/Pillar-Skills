---
name: revision-history-review
description: Review controlled documents (SOPs, WIs, forms, specifications, protocols, reports; .docx or .pdf) for revision consistency before approval. Checks (1) the file name matches the page header (doc #, Rev, title), (2) the latest Rev in the revision history table matches the header/file-name Rev, (3) the changes described in the revision history table are actually present in the document content, (4) reports "no Rev. history Table of <file>" when the table is missing, (5) outputs a File / Discrepancy table, and (6) when an old revision is also attached, diffs old vs new and confirms the revision history entry matches the real changes (nothing undocumented, nothing claimed but not made). Trigger on "review revision history", "rev history", "check revision", "doc review", "compare old and new version", "redline check", or when one or more controlled documents are uploaded for review.
---

# Revision History Review

Purpose: catch revision-control errors before a document goes for approval. Typical
errors: the file name and header disagree, the header was bumped to Rev 3 but nobody
added a Rev 3 row to the table, or the table says "changed X" but X was never changed,
or a change was made and not recorded.

The script does the mechanical comparisons. Checking the content against the change
descriptions is done by Claude, reading the document. Every discrepancy reported must
cite what was found (quote the text, give the section).

## Workflow

### Step 1 – Identify the files

- List every uploaded file. Group files that share a document number (e.g.
  `SOP-0012 ... Rev 2.docx` and `SOP-0012 ... Rev 3.docx`). Within a group, the
  file with the **higher Rev in its file name/header** is the new version and the
  others are old versions (function 6). Files with no partner are reviewed alone.
- `.doc` files: convert first: `soffice --headless --convert-to docx <file>`.
- Screenshots / images: read them directly and apply the same checks by hand.

### Step 2 – Extract (every file)

```bash
python3 <skill_dir>/scripts/extract_doc.py <file1> [<file2> ...] --out <scratch_dir>
```

For each file this prints the doc #/Rev/title parsed from the **file name** and the
**header**, the latest Rev in the revision history table, and the automated checks.
It writes `<scratch_dir>/<file stem>.json` with:

- `file_name`, `headers` (every header instance, so a Rev mismatch on one section
  shows), `header_summary`
- `revision_history` – every row: `rev`, `date`, `description`
- `latest_rev_in_table`, `latest_change_description`
- `auto_checks` – results with ids 1a–1d, 2a–2e, 3a, 4 (see below)
- `body` – headings, paragraphs and tables in order, used for the content check

Treat `auto_checks` as a first pass, not the verdict: confirm each FAIL by looking at
the extracted text (a parsing miss is not a document error), and resolve every
REVIEW yourself. If the script finds no table but the document plainly has one
(e.g. a scanned PDF), read the pages with the Read tool and continue manually.

### Step 3 – Run the checks

**Function 1 – File name vs header**
Compare the document number, Rev and title in the file name with the page
header (check 1a doc #, 1b Rev, 1c Rev is the same on every header, 1d title).
Title wording differences such as "&" vs "and", or a shortened title, are an
Observation unless the document number/title clearly refers to a different
document. A missing Rev in the file name is reported if the company convention puts
it there (it does when other files in the set include it).

**Function 2 – Latest Rev in table vs document Rev**
The highest Rev in the revision history table must equal the header Rev (2a) and
the file name Rev (2b). Also report: rows out of order (2c), duplicate Rev rows
(2d), skipped Rev numbers (2e, REVIEW: may be legitimate if a Rev was cancelled),
and a latest row with an empty description (3a). Check the date of the latest row is
filled in, or reads as a placeholder such as "TBD"/"at release" per company practice.

**Function 3 – Revision history entries vs content**
For the **latest** Rev entry (and for earlier entries where a check is quick), split
the description into individual claimed changes. For each claim:
- Find the section/text it refers to in `body` and confirm the document now reads
  as described (e.g. "changed approval time to 10 days" → the procedure must say
  10 days, not 7).
- Confirm referenced section numbers, table/figure numbers, document numbers and
  form numbers exist and are correct ("Added Section 6.3" → there is a 6.3).
- Flag vague entries that cannot be verified ("minor updates", "editorial changes")
  as an Observation and ask for specifics.
- Without an old version you can only confirm the claim is **consistent** with the
  current content, not that it was really changed. Say so in the report.

**Function 4 – No revision history table**
If check 4 is FAIL (and you confirmed it by reading the document), report exactly:

> no Rev. history Table of <file name>

and still run Function 1 for that file. Skip Functions 2, 3 and 6 for it.

**Function 6 – Old version attached**
For each old/new pair:

```bash
python3 <skill_dir>/scripts/compare_versions.py <old_file> <new_file> --out <scratch_dir>
```

This writes `diff_<old>__<new>.md` / `.json`: old vs new Revs, the revision history
rows added since the old version, and every body change by section with word-level
markup (`[-removed-]` `{+added+}`). The revision history table itself is excluded
from the body diff. Then:
- Confirm the Rev went up by one step from old to new (file name, header, table).
  The old version's latest table row should still be present, unchanged, in the
  new version. Flag edits to old rows.
- Map **every** body change to a claim in the new revision history row(s), and map
  **every** claim to a body change:
  - change with no claim → "Undocumented change"
  - claim with no change, or a change that differs from the claim (e.g. claim says
    10 days, diff shows 5 → 7) → "Claimed change not made / not as described"
- Header/footer, page-number, date-field and formatting-only changes are not
  required in the table; list them as Observations only if substantive.

### Step 4 – Output

Always produce this table first (function 5). One row per discrepancy; a file with
no discrepancies gets a single row saying "No discrepancies found".

```
| File | Discrepancy |
|---|---|
| SOP-0012 Document Control Rev 3.docx | Header is Rev. 3 but the latest revision history entry is Rev 2 (no Rev 3 row). |
| SOP-0012 Document Control Rev 3.docx | Rev 2 entry says "approval time changed to 10 days"; Sec 2 Step 2 reads "within 7 days" (old version: 5 days). |
| SOP-0012 Document Control Rev 3.docx | Rev 2 entry says "Added Section 2 Step 3 on training"; no Step 3 exists in Section 2. |
| WI-0100 Label Printing Rev 1.docx | no Rev. history Table of WI-0100 Label Printing Rev 1.docx |
```

Write each discrepancy so it stands alone: what the table/file name/header says,
what the document actually says, and where (section, page or table row). Then,
after the table:

1. **Summary per file**: doc #, header Rev, file name Rev, latest table Rev,
   and PASS/FAIL for Functions 1, 2, 3 (and 6 when an old version was given).
2. **Change traceability** (only when an old version was given):
   `| # | Section | Change found (old → new) | Matching rev history claim | Result |`
3. Anything you could not verify, such as an unreadable scan or content in images,
   stated plainly. Never guess at text you cannot read.

Save the output to a markdown file if the user wants a record (see
`examples/SOP-0012-Rev3-review.md`).

## Notes

- Rev formats: numeric (`1`, `01`, `2.1`) and letter (`A`, `B`, `AA`) revs are
  both understood. `01` and `1` count as the same Rev. A document whose header uses
  letters while the table uses numbers is a discrepancy.
- The script finds the revision history table by its header row (a `Rev`/`Revision`/
  `Version` column plus a description/change column), preferring a table under a
  "Revision History" / "Document History" / "Change History" heading and the last
  such table in the document.
- This skill checks consistency only. It does not judge whether the change itself is
  technically correct or properly approved.
