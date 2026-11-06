# Are recent ebhāratī-sampat PDFs gaining text?

**Status: complete. Checked 2026-10-21, every book in scope.** Delete this file
once its findings have been promoted or published.

## Question

Our metadata scrape of ebharatisampat.in (11–12 August 2026) found that most
recent uploads are PDF scans with no searchable text: about half of uploads
since 2024, and about 94% of 2026 uploads. Does the site add text to these
later, and if so, how soon and how much? A paper in draft says:

> These recently added PDF-only items may well gain searchable text soon; our
> understanding of the collection history is not yet fine-grained enough to
> determine whether OCR happens along the way or in retrospective batches.

This check is a first answer to that.

## Short answer

**Yes, but only a trickle so far, and only for the oldest of the 2026 uploads.**
Ten weeks after our scrape, 9 of the 2,494 books uploaded in 2026 as PDF-only
had gained text. All 9
were uploaded between 16 January and 4 March 2026. No book uploaded from April
onward has gained text, and none of the 147 books added since our scrape
arrived with any.

## Method

- **What "has text" means.** A book's metadata page on the site shows a
  "Read Unicode" link to a text reader when the site holds text for it, and a
  "Read E-Book" link when it holds a PDF scan. "PDF-only" means only the second
  link is there. This is the same definition the paper's figures use. We do
  **not** look inside the PDFs, so a PDF that gained a hidden text layer without
  a text reader appearing would not show up here.
- **Baseline.** Our scrape of every book's metadata page, 11–12 August 2026
  (11,066 books, the newest uploaded 10 August).
- **Recheck.** On 2026-10-21 we fetched the metadata page again for every 2026
  upload that was PDF-only in the baseline. Requests were spaced 2 seconds
  apart.
- **Controls.** We also refetched 8 randomly chosen 2026 books that had text in
  the baseline. All 8 still showed it, which confirms the recheck detects text
  correctly.
- **New books.** The site numbers books with consecutive serials. Our baseline
  ends at serial 12879. On the live site the newest serial is 13026, and
  13027–13031, 13039 and 13071 do not exist. Every serial from 12880 to 13026
  exists and maps to exactly one book, so exactly **147** books have been added
  since our scrape. We fetched all 147 metadata pages.

## Results

### 2026 uploads that were PDF-only in August

In the baseline, 2,667 books carried a 2026 upload date. 173 of them already
had text. The other 2,494 were PDF-only, and those are the books rechecked.

| Upload month (2026) | PDF-only in Aug. baseline | Rechecked | Now have text |
|---|---|---|---|
| January | 104 | 104 | 2 |
| February | 137 | 137 | 6 |
| March | 115 | 115 | 1 |
| April | 141 | 141 | 0 |
| May | 495 | 495 | 0 |
| June | 564 | 564 | 0 |
| July | 662 | 662 | 0 |
| August (1–10) | 276 | 276 | 0 |
| **Total** | **2,494** | **2,494** | **9** |

No rechecked book has lost its PDF.

The 9 books that gained text:

| Serial | Uploaded | Text reader |
|---|---|---|
| 10274 | 2026-01-16 | flat text |
| 10285 | 2026-01-16 | flat text |
| 10405 | 2026-02-07 | flat text |
| 10414 | 2026-02-12 | flat text |
| 10434 | 2026-02-14 | flat text |
| 10485 | 2026-02-24 | flat text |
| 10496 | 2026-02-25 | flat text |
| 10497 | 2026-02-25 | flat text |
| 10545 | 2026-03-04 | flat text |

### Books added since our scrape

| Upload month (2026) | Books | With text |
|---|---|---|
| August (11–31) | 135 | 0 |
| September (1–15) | 12 | 0 |
| **Total** | **147** | **0** |

The newest upload is dated 15 September 2026, so nothing seems to have been
added in the five weeks before the check. Uploads have also slowed sharply:
147 in the ten weeks after 10 August, against about 2,667 in the first seven
months of 2026.

## Interpretation, with the strength of each claim

- **Supported:** text is added after upload, not only at upload. Nine books
  that were PDF-only in August have a text reader in October.
- **Supported:** so far the backfill is small: 9 of 2,494 (0.4%) of the 2026
  PDF-only books, or 9 of 356 (2.5%) among those uploaded January–March.
- **Suggestive, not established:** the backfill looks like retrospective
  batches working forward through upload dates. The hits are confined to the
  oldest uploads (16 January – 4 March) and cluster closely by date and serial,
  with three on 24–25 February. Nothing newer has gained text yet. Two
  observations ten weeks apart cannot show a steady process or measure its
  pace. That needs repeated checks.
- **Not shown:** whether the new text is OCR, typed in by hand, or imported
  from elsewhere, and whether it has been proofread. The site does not say how
  text was produced, and we have not inspected it. Say "gained searchable
  text" or "gained a text version", not "was OCR'd", unless someone checks.
- **Not shown:** anything about books uploaded before 2026. Only 2026 uploads
  were rechecked.

## Caveats for public writing

- The site exposes no version history, so we only know each book's state at
  our two checks, not when its text actually appeared.
- Upload dates come from the cover-image filenames on the site, the only
  upload-date information it exposes.
- The site's own listings and headline counts are unreliable, so do not
  reconcile these figures against them. Everything here comes from individual
  book pages.
- Name the site as ebharatisampat.in (ebhāratī-sampat). Serials are the site's
  own "Ebharati-NNNNN" numbers, so readers can look the books up.
