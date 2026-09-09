# Reading the serial axis

The band analysis itself is **published live** on the About page under "By
Serial Number", and regenerated on demand:

    python notes/samples/serial-bands.py [--gaps|--edges|--rho|--coverage]

What is not on the page is how to avoid misreading it.

**Serial is a time axis.** Spearman ρ(serial, `uploaded`) = **0.9716** across
the 11044 dated works; only 6.6% of adjacent serial pairs go backwards in date.
That is what makes bands meaningful at all — and it is also why a statistic
sampled from a contiguous serial range describes an **era, not the corpus**.

**`uploaded` is inferred, not published.** It comes from a thumbnail filename
convention (`pipeline/upload_dates.py`), not a documented field, and that
convention already changed once mid-2023 without announcement. Coverage is
11044/11066 (99.7%). Re-verify it on each pull.

**Thin bands are sample artifacts.** The high-serial bands rest on far fewer
measured works than they contain — a low median there is a property of what has
been fetched, not of the texts.

**`chunks` is not a size or depth signal.** It is fetch-pass bookkeeping: over a
thousand books have `chunks: 1` with more than 200k characters. Deliberately
absent from the table.

**Sizes cover completed books only**, so every median is a mild underestimate
wherever a band is not fully fetched.
