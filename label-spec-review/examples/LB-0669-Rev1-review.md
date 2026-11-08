# Label Review – LB-0669 Rev. 1 – Fetal Antigen NIPT BOX 1 Label - LOT

Source: screenshots of pages 1–2 (Sec 1–2 and Figure 1). The label artwork is printed twice:
copy A is rotated 180° at the top, and copy B is upright at the bottom. Both copies were checked.

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Symbols correct & accurate | **FAIL (minor)** | All 9 listed symbols appear on the artwork with the correct graphics. ISO citation format is inconsistent: `ISO-15223-1-2021` ×4 and `ISO-15223-1:2021` ×4. The correct form is `ISO 15223-1:2021`. |
| 2 | Sec 2 items all on artwork | **PASS** | All 1 Artwork, 9 Symbols and 22 Information items were found on both copies (see the traceability table). |
| 3 | Artwork aligned with Sec 2 | **FAIL (minor)** | The UDI dates are specified as `YY-MM-DD`, but the artwork prints `231025` / `231023` (GS1 `YYMMDD`). No content on the artwork is missing from Sec 2. |
| 4 | LB# / Rev consistent | **PASS** | Header p1: `LB-0669` / `Rev. 1`; header p2: `LB-0669` / `Rev. 1`; Sec 2: `LB-0669, Rev. 1`; artwork copy A: `LB-0669 Rev. 1`; copy B: `LB-0669 Rev. 1`. The header title "BOX 1" matches "Box 1 of 4". |

## Item-by-item traceability

| Sec 2 item | Expected | Copy A (rotated) | Copy B | Result |
|---|---|---|---|---|
| Company logo and name | Pillar Biosciences logo | ✓ | ✓ | PASS |
| Manufacturer symbol | Filled factory + name/address | ✓ | ✓ | PASS |
| Caution symbol | Triangle with ! | ✓ | ✓ | PASS |
| Expiration date symbol | Hourglass + date | ✓ 2023-10-25 | ✓ 2023-10-25 | PASS |
| Temperature limit symbol | Thermometer, -25°C / -15°C | ✓ | ✓ | PASS |
| Positive control symbol | `CONTROL +` | ✓ | ✓ | PASS (see O1) |
| REF symbol | `REF` PB-0108 | ✓ | ✓ | PASS |
| LOT symbol | `LOT` [Lot Number] | ✓ | ✓ | PASS |
| Contains sufficient for <n> tests | Σ 24 | ✓ | ✓ | PASS |
| IUO symbol | `IUO` + "Investigational Use Only" | ✓ | ✓ | PASS |
| Product name | alloReveal Fetal Antigen NIPT Panel HDA-IM-2001-24 | ✓ | ✓ | PASS |
| Box 1 of 4 | Box 1 of 4 | ✓ | ✓ | PASS |
| Investigational Use Only | text | ✓ | ✓ | PASS |
| REF: PB-0108 | PB-0108 | ✓ | ✓ | PASS |
| LOT: [Lot Number] | [Lot Number] | ✓ | ✓ | PASS |
| Pillar Biosciences, Inc. | | ✓ | ✓ | PASS |
| www.pillarbiosci.com | | ✓ | ✓ | PASS |
| 9 Strathmore Rd, Natick MA 01760 USA | | ✓ | ✓ | PASS |
| +1-800-514-9307 | | ✓ | ✓ | PASS |
| Manufacturing date YYYY-MM-DD | "Manufactured 2023-10-23" | ✓ | ✓ | PASS |
| Country of Origin: USA | | ✓ | ✓ | PASS |
| Expiration date YYYY-MM-DD | 2023-10-25 | ✓ | ✓ | PASS |
| Temperature range -25°C to -15°C | | ✓ | ✓ | PASS |
| Sufficient for 24 tests | Σ 24 | ✓ | ✓ | PASS |
| 2D barcode (UDI) | Data Matrix/QR | ✓ | ✓ | PASS |
| UDI – Lot number | (10) | ✓ `(10)LotNumber` | ✓ | PASS |
| UDI – Expiration date (YY-MM-DD) | (17) | `(17)231025` | `(17)231025` | **Format mismatch (m2)** |
| UDI – Date of manufacture (YY-MM-DD) | (11) | `(11)231023` | `(11)231023` | **Format mismatch (m2)** |
| UDI dates vs. printed dates | (17)=use-by, (11)=mfg | 231025 ⇔ 2023-10-25, 231023 ⇔ 2023-10-23 | same | PASS |
| Label part number and revision | LB-0669, Rev. 1 | ✓ | ✓ | PASS |

## Findings

| ID | Severity | Location | Finding | Suggested correction |
|---|---|---|---|---|
| m1 | Minor | Sec 2 › Symbols | The ISO citation format is inconsistent: Manufacturer, Caution, Expiration Date and Temperature Limit use `ISO-15223-1-2021`, while the others use `ISO-15223-1:2021`. | Use `ISO 15223-1:2021` for all of them. |
| m2 | Minor | Sec 2 › UDI Information | The spec gives the UDI expiration and manufacture dates as `YY-MM-DD`. The artwork correctly uses GS1 `YYMMDD` (`231025`), so the spec and artwork disagree. | Change the spec to `YYMMDD`. |
| O1 | Observation | Artwork, right side | `CONTROL +` sits directly under the expiration date, so it may read as part of the date. Confirm that Box 1 actually contains the positive control. | Add spacing or group it with the product identity. |
| O2 | Observation | Artwork | The yellow "(This is an Example)" callouts overlap the expiration date (copy B) and the label border. | Confirm that the callouts are not part of the approved printable file. |
| O3 | Observation | Artwork copy A | The UDI text kerning is uneven (`23 10 25`). | Cosmetic; check the printable file. |
