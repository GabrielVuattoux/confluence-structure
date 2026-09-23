# confluence-structure

**Read Confluence storage-format exports without losing their structure.**

Confluence keeps pages in an XHTML dialect with its own namespaces — `ac:` for macros and
markup, `ri:` for resource identifiers. An export in that format carries more than the
rendered page does: a status icon is a tag with a name attribute, merged cells are declared
rather than painted, and a macro records what it would have generated.

Extract the text and all of it is gone. Silently, which is the problem.

```python
>>> from confluence_structure.parser import parse_html
>>> cell = '<td><ac:emoticon ac:name="tick" /></td>'
>>> lxml.html.fromstring(cell).text_content()
''                                    # what a text-only read sees
>>> parse_html(f'<table><tbody><tr>{cell}</tr></tbody></table>').icon_count
1                                     # what is actually there
```

---

## What it costs to read a page as text

Measured on the demo corpus in this repository, so the figures can be checked rather than
believed:

| approach | values read | icon states | misplaced | usable |
|---|---|---|---|---|
| text only — `html2text`, `get_text()` | 380 | 0 | 380 | **0.0%** |
| tables, text cells, spans ignored | 380 | 0 | 32 | 57.3% |
| tables, text cells, spans expanded — `pandas.read_html` | 380 | 0 | 0 | 62.6% |
| **attribute-aware — this library** | **607** | **227** | 0 | **100%** |

```bash
python -m confluence_structure.comparison
```

A value counts as usable only if it was read **and** landed under the column it belongs to.
Both halves are required: a value read correctly and filed under the wrong heading is not a
partial success — it is an answer that looks complete and describes the wrong thing.

**Two costs, and they fail differently.** A cell whose only content is an icon comes back
empty from every text-based reader; the answer is visibly incomplete, which someone
notices. A cell shifted by a merged cell looks right and is not.

The three baselines are reimplemented here so the measurement needs no runtime dependency.
Tests run the real tools where installed and check both halves of the substitution: that
each loses what the baseline says it loses, and that the span-expanding baseline puts a
value in the same column `pandas` does.

Figures depend on how icon-heavy a corpus is — 37% of the values in this one are icons —
and the measurement covers table content only. Reading prose as text loses nothing.

---

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Two runtime dependencies: `lxml` and `pydantic`. The rest is for tests.

## Reading a page

```python
from pathlib import Path
from confluence_structure.parser import parse_file

page = parse_file(Path("export/1040000.html"))

page.sections        # prose, split at its headings
page.tables          # expanded grids, merged cells resolved
page.legend          # what the page says its own icons mean, if it says
page.figures         # diagrams, with whatever text could be read out of them
page.references      # page links (by title) and external URLs
page.attachments     # files the page depends on, and how it refers to them
page.macros          # including those whose body only exists at render time

page.trustworthy     # False if any table's geometry did not resolve cleanly
```

Reading a value with the meaning its page gives it:

```python
table = page.tables[0]
labels = table.column_labels()

for cell in table.body_rows()[0]:
    if cell.icons:
        state = cell.icons[0].name
        meaning = page.legend.meaning_of(state) if page.legend else None
        print(labels[cell.col], "→", meaning or state)

# Receiving Checks Seal Integrity → required on every shipment
# Receiving Checks Temperature Log → not applicable here
# Receiving Checks Hazard Labelling → required above 500 kg
```

---

## How it works

### Icons carry state, and there are two encodings

The documented form is `<ac:emoticon ac:name="tick"/>`. The tag is empty, so all of its
meaning is in the attribute, and text extraction returns nothing.

The second form is easy to miss. An author who *pastes* an icon rather than inserting one
gets an inline image pointing at the same icon set — and Confluence's icon **files are not
named after its emoticons**. Paste a cross and the page gets `error.svg`, not `cross.svg`.
A reader handling only the documented tag never encounters `error` at all.

Names that merely look alike are kept apart for the same reason. `cross` and `error` render
identically in many themes, as do `tick` and `check`; treating them as one is an assumption
about rendering, not a fact in the file.

### Merged cells are expanded, so a value keeps its column

An HTML table is not a grid. A cell may declare `colspan` or `rowspan` and occupy several
positions, and every later cell in that row shifts to make room:

```html
<tr><th rowspan="2">Class</th><th colspan="2">Checks</th></tr>
<tr><th>Seal</th><th>Weight</th></tr>
```

Row 1 declares two cells, but its first column is already taken. Number its cells 0, 1 and
**"Seal" lands under "Class"**.

So the table is expanded into a dense matrix. A merged cell fills every position it covers
and the copies are marked, which keeps two things true at once: a lookup by column always
lands on the right value, and anything countable is still counted once.

### Problems are reported, never repaired

Two invariants are checked per table:

- **every row covers every column** — a row that does not is flagged rather than patched,
  because filling the gap means guessing where it belongs. A row with 2 of 3 columns yields
  three plausible grids, and picking one is exactly the silent error this library exists to
  prevent;
- **every cell resolves** to text, to a known icon state, or to nothing.

A table failing either is marked untrustworthy. The caller decides what to do; the library
will not quietly produce a plausible grid from an implausible one.

An undeclared header row is only a note — the values are still trustworthy, we just do not
know what the columns are called.

### Meaning comes from the page, or not at all

Reading `ac:name="warning"` is certain. Knowing what `warning` means *in that table* is not.
Unless the page says, which authors who build tables out of icons routinely do:

> **Legend:** ✓ always required  ⚠ required above 500 kg  ✗ not applicable here

A legend is recognised by shape rather than by the word "legend" — which is not always
there, and not always English. What identifies one is a run of at least two icons each
followed by a short phrase, outside any table. Icons *inside* a table are values, not
statements about icons. A lone icon in a sentence is prose. A "meaning" with no letters is
a footnote marker. Two legends that disagree cancel each other, because picking a side
invents a meaning the page never gave.

Where no legend exists, the state travels unread. That is the honest alternative.

### A figure is either unread or unreadable

A drawing stored as SVG keeps its labels as text nodes, so reading a process diagram needs
no vision model — inline `<svg>` and the `data:image/svg+xml` form both parse. Failing
that, author-written alternative text is often a better description of a process than the
paragraph beside it; alternative text that is merely the file name is discarded, because
counting `image-2025-3-28.png` as a description makes an unreadable figure look readable.

When the content is in a separate binary the export does not include, **no parser recovers
it**, and calling that a parsing failure would be wrong — it is a delivery problem. The two
are distinguished so a caller can tell "we did not look" from "there is nothing to look at".

Confluence's `drawio` macro is the second case wearing the clothes of the first: the storage
format keeps the diagram's *name* and its display settings, never its XML.

### Page links name titles, not files

A Confluence link names its target by **title**, while an export names its files by **page
id**, and nothing in the export bridges the two — that needs the index which usually ships
alongside. So titles are kept verbatim rather than turned into paths that might be wrong.

Macros whose body is produced at render time are marked, so a caller can tell a genuinely
short page from one whose content simply is not in the file.

---

## The demo corpus

`corpus/` holds 27 synthetic Confluence pages — a warehouse operations handbook for an
invented logistics company — generated by `tools/build_demo_corpus.py`. The fiction is
beside the point; the structure is the whole point. It deliberately contains:

| | |
|---|---|
| merged cells | a value belongs to a column it does not sit in |
| both icon encodings | including a state that exists only in the pasted one |
| a page-declared legend | so meaning can come from the source |
| configuration matrices | reference data authored as page layout |
| a readable diagram | SVG, labels as text |
| unreadable diagrams | a missing binary, and a drawio macro |
| dangling references | links to pages the export does not contain |
| generated macros | a page whose body only appears at render time |
| two authoring defects | a row missing a column, an icon outside the standard set |

```bash
python tools/build_demo_corpus.py
```

Output is deterministic — no randomness, no timestamps — and the generated pages are
committed. A change in the generator then shows up as a diff in the corpus *and* in the
published numbers, instead of silently moving both. A test asserts that regenerating an
unchanged corpus produces no diff.

---

## What this does not do

- **Resolve page links.** The index that maps titles to files ships separately with a real
  export; this library reports the titles and leaves the mapping to the caller.
- **Read images.** A diagram whose labels are only in a PNG stays unread, and is reported
  as such rather than guessed at.
- **Render macros.** A macro that builds its body at display time is marked, not executed.
- **Interpret anything.** No icon acquires a meaning the page did not give it.

## Tests

```bash
.venv/bin/pytest -q          # 115 tests
.venv/bin/ruff check .
.venv/bin/mypy
```

The suite runs against the committed corpus, so it covers the awkward cases on pages you
can open and read.

## Licence

MIT.
