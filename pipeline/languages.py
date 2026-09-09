"""Normalizing ebharatisampat.in's free-text `language` field.

The site records language as an unconstrained string, so one language has
several spellings and a multi-language book is just those spellings joined by
whitespace in no fixed order. Observed 2026-08-10: **81 distinct values for
about 20 languages** (60 in the site's own facet sidebar, 26 in our snapshot,
overlapping).

The variation is of four kinds:

1. **spelling** -- English is `आङ्ग्लम्`, `आङ्गलम्`, and `आड्गलेयम्`; Tamil has
   four forms; Gujarati three
2. **anusvāra vs -म्** -- `संस्कृतं` alongside `संस्कृतम्`, `आङ्ग्लं` alongside
   `आङ्ग्लम्`
3. **whitespace** -- a double space in `संस्कृतम्  हिन्दी`, a literal tab in
   `संस्कृतम्\tजर्मन्`
4. **order** -- both `संस्कृतम् आङ्ग्लम्` and `आङ्ग्लम् संस्कृतम्` occur

So the field is parsed as a *set* of languages rather than matched as a string:
split on whitespace, normalize each token, discard what doesn't resolve. Exact
string matching silently drops books, which is the failure this exists to
prevent.

`is_sanskrit()` is the scope test for the atlas: **a book is in scope if
Sanskrit appears at all**, not only if it is the sole language. 1253 books on
the site are Sanskrit alongside another language -- mostly a Sanskrit text with
an English introduction or facing translation -- and excluding them would throw
away far more than the 292 books that carry no Sanskrit.
"""

import unicodedata

SANSKRIT = "sanskrit"

# Token -> canonical name. Every spelling below was observed in the site's
# language facet or in the snapshot; this is a record of what exists, not a
# guess at what might. Unrecognized tokens are reported by `unknown_tokens()`
# rather than silently dropped, so new spellings surface instead of vanishing.
TOKENS = {
    # Sanskrit -- incl. anusvāra form and a bare typo (`संस्कृतम`, 1 book)
    "संस्कृतम्": SANSKRIT,
    "संस्कृतं": SANSKRIT,
    "संस्कृतम": SANSKRIT,
    # English
    "आङ्ग्लम्": "english",
    "आङ्गलम्": "english",
    "आङ्ग्लं": "english",
    "आङ्गलं": "english",
    "आड्गलेयम्": "english",
    # Indic
    "हिन्दी": "hindi",
    "मराठी": "marathi",
    "गुजराती": "gujarati",
    "गुजराति": "gujarati",
    "गुर्जरा": "gujarati",
    "वङ्गभाषा": "bengali",
    "अस्सामी": "assamese",
    "कोङ्कणी": "konkani",
    "अवधी": "awadhi",
    "उर्दू": "urdu",
    "तमिल्": "tamil",
    "तमिळ्": "tamil",
    "तामिल्": "tamil",
    "तामिलः": "tamil",
    "तेलुगुः": "telugu",
    "कन्नडम्": "kannada",
    "मलयालम्": "malayalam",
    # Other Indic-sphere classical languages
    "प्राकृतम्": "prakrit",
    "प्राकृत": "prakrit",
    "पालिः": "pali",
    "पाली": "pali",
    "टिबेटन्": "tibetan",
    "टिबेटियन्": "tibetan",
    # European / other
    "जर्मन्": "german",
    "फ्रेञ्च्": "french",
    "लाटिन्": "latin",
    "इटालियन्": "italian",
    "चैनीस्": "chinese",
    "हिब्रू": "hebrew",
}


def _clean(token: str) -> str:
    """NFC-normalize and strip punctuation the field sometimes carries."""
    return unicodedata.normalize("NFC", token).strip().strip(",;/|")


def parse(value: str) -> set[str]:
    """Return the set of canonical languages named in one `language` value.

    Splits on any whitespace (covering the double-space and literal-tab cases),
    so word order never matters. Unrecognized tokens are omitted -- use
    `unknown_tokens()` to find them.
    """
    if not value:
        return set()
    return {TOKENS[t] for t in map(_clean, value.split()) if t in TOKENS}


def unknown_tokens(value: str) -> set[str]:
    """Tokens in `value` that no rule above recognizes.

    Run this across a fresh pull before trusting counts: a new spelling shows up
    here rather than quietly shrinking a total.
    """
    if not value:
        return set()
    return {t for t in map(_clean, value.split()) if t and t not in TOKENS}


def is_sanskrit(value: str) -> bool:
    """Whether a book is in scope for this atlas: any Sanskrit at all."""
    return SANSKRIT in parse(value)
