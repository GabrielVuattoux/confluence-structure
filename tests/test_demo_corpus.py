"""The demo corpus is a fixture with a job: it must contain what it claims to contain.

Every published measurement is taken on these pages, so if the corpus quietly stopped
holding a merged cell or a pasted icon, the numbers would keep being produced and stop
meaning anything.
"""

import csv
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from confluence_structure.parser import parse_file

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
PAGES = CORPUS / "pages"


@pytest.fixture(scope="module")
def pages():
    return [parse_file(path) for path in sorted(PAGES.glob("*.html"))]


@pytest.fixture(scope="module")
def index():
    with (CORPUS / "index.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# --- the corpus holds what the measurements assume ---


def test_every_page_parses(pages):
    assert len(pages) == 24
    assert all(page.sections for page in pages)


def test_merged_cells_are_present_and_resolved(pages):
    spanned = sum(1 for p in pages for t in p.tables for r in t.grid for c in r if c.spanned)
    assert spanned > 20, "without merged cells the corpus cannot show a value drifting"


def test_both_icon_encodings_are_present(pages):
    encodings = Counter(
        icon.encoding
        for page in pages
        for table in page.tables
        for row in table.grid
        for cell in row
        if not cell.spanned
        for icon in cell.icons
    )
    assert encodings["emoticon"] > 100
    assert encodings["image"] >= 3, "a pasted icon is the case a naive reader misses"


def test_one_state_exists_only_in_the_pasted_encoding(pages):
    """Confluence's icon files are not named after its emoticons.

    Paste a cross and the page gets `error.svg`. A reader that handles only the documented
    tag never sees `error` at all — which is why the two vocabularies are kept apart.
    """
    by_name = Counter(
        (icon.name, icon.encoding)
        for page in pages
        for table in page.tables
        for row in table.grid
        for cell in row
        if not cell.spanned
        for icon in cell.icons
    )
    assert by_name[("error", "image")] >= 3
    assert by_name[("error", "emoticon")] == 0


def test_a_readable_and_an_unreadable_diagram_are_both_present(pages):
    kinds = Counter(figure.kind for page in pages for figure in page.figures)
    assert kinds["inline_svg"] >= 1, "labels readable as text"
    assert kinds["attachment"] >= 1, "labels in a file the export does not carry"
    assert kinds["drawio"] >= 1, "a macro that keeps the diagram's name and nothing else"


def test_a_macro_that_builds_its_body_at_render_time_is_present(pages):
    generated = [m.name for page in pages for m in page.macros if m.generates_content]
    assert set(generated) >= {"pagetree", "children"}


def test_a_table_without_a_declared_header_is_present(pages):
    headerless = [t for p in pages for t in p.tables if not t.header_rows]
    assert len(headerless) == 1
    assert any(pb.code == "no_header_row" for pb in headerless[0].problems)


def test_exactly_two_pages_are_untrustworthy_and_for_the_stated_reasons(pages):
    flagged = {
        page.page_id: sorted(
            {pb.code for t in page.tables for pb in t.problems if pb.severity == "blocking"}
        )
        for page in pages
        if not page.trustworthy
    }
    assert sorted(flagged.values()) == [["incomplete_row"], ["unknown_icon"]]


def test_the_matrix_page_is_clean(pages):
    """The showcase page must not carry a defect of its own."""
    matrix_page = max(pages, key=lambda p: p.icon_count)
    assert matrix_page.trustworthy
    assert len(matrix_page.tables) == 4, "one table per warehouse"


def test_a_value_stays_under_its_column_on_the_matrix_page(pages):
    matrix_page = max(pages, key=lambda p: p.icon_count)
    table = matrix_page.tables[0]
    labels = table.column_labels()
    first = table.body_rows()[0]
    found = {labels[c.col]: (c.text or "/".join(i.name for i in c.icons)) for c in first}
    assert found["Shipment Class"] == "Standard"
    assert found["Receiving Checks Seal Integrity"] == "tick"


# --- the index, and what it cannot resolve ---


def test_the_index_names_every_page(pages, index):
    assert {row["filename"] for row in index} == {f"{p.page_id}.html" for p in pages}


def test_some_references_point_at_pages_the_corpus_does_not_contain(pages, index):
    """What a dangling reference looks like from the inside: a title nothing resolves."""
    titles = {row["title"] for row in index}
    referenced = {r.target for p in pages for r in p.references if r.kind == "page"}
    dangling = referenced - titles
    assert dangling == {"Carrier Onboarding", "Segregation Matrix"}


def test_page_links_name_titles_not_files(pages):
    """Which is why the index exists at all."""
    targets = [r.target for p in pages for r in p.references if r.kind == "page"]
    assert targets and not any(t.endswith(".html") for t in targets)


# --- reproducibility ---


def test_regenerating_the_corpus_changes_nothing():
    """A published number must not move because the generator was run again."""
    before = {p.name: p.read_bytes() for p in sorted(PAGES.glob("*.html"))}
    index_before = (CORPUS / "index.csv").read_bytes()

    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_demo_corpus.py")],
        check=True,
        capture_output=True,
    )

    after = {p.name: p.read_bytes() for p in sorted(PAGES.glob("*.html"))}
    assert after == before
    assert (CORPUS / "index.csv").read_bytes() == index_before
