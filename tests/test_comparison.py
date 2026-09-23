"""The measurement, and a check that the baselines behave like the tools they stand for."""

import io
from pathlib import Path

import lxml.html
import pytest

from confluence_structure.comparison import (
    APPROACH_LABELS,
    columns_expanding_spans,
    columns_ignoring_spans,
    compare,
    source_rows,
)

CORPUS = Path(__file__).resolve().parents[1] / "corpus" / "pages"

MATRIX = """<table><tbody>
<tr><th rowspan="2">Class</th><th colspan="2">Checks</th></tr>
<tr><th>Seal</th><th>Weight</th></tr>
<tr><td>Standard</td>
    <td><ac:emoticon ac:name="tick" /></td>
    <td><ac:emoticon ac:name="cross" /></td></tr>
</tbody></table>"""


@pytest.fixture(scope="module")
def report():
    return compare(sorted(CORPUS.glob("*.html")))


# --- the two costs ---


def test_no_text_based_approach_recovers_an_icon(report):
    by_approach = {r.approach: r for r in report.results}
    assert report.icon_values > 200
    for approach in ("TEXT_ONLY", "TABLE_TEXT", "TABLE_TEXT_SPANS"):
        assert by_approach[approach].icon_states_read == 0
    assert by_approach["ATTRIBUTE_AWARE"].icon_states_read == report.icon_values


def test_only_the_approach_that_ignores_merged_cells_misplaces_values(report):
    by_approach = {r.approach: r for r in report.results}
    assert by_approach["TABLE_TEXT"].values_misplaced > 0
    assert by_approach["TABLE_TEXT_SPANS"].values_misplaced == 0
    assert by_approach["ATTRIBUTE_AWARE"].values_misplaced == 0


def test_text_only_never_keeps_a_column(report):
    """Stripping markup keeps the words and loses the grid they were arranged in."""
    text_only = next(r for r in report.results if r.approach == "TEXT_ONLY")
    assert text_only.values_misplaced == text_only.values_read
    assert text_only.usable(report.values) == 0.0


def test_this_library_reads_every_value_and_keeps_every_column(report):
    ours = next(r for r in report.results if r.approach == "ATTRIBUTE_AWARE")
    assert ours.values_read == report.values
    assert ours.usable(report.values) == 1.0


def test_every_approach_is_reported(report):
    assert {r.approach for r in report.results} == set(APPROACH_LABELS)
    assert "misplaced" in report.render()


def test_a_corpus_without_tables_costs_nobody_anything(tmp_path: Path):
    (tmp_path / "prose.html").write_text("<h2>Scope</h2><p>Only words.</p>", encoding="utf-8")
    quiet = compare(sorted(tmp_path.glob("*.html")))
    assert quiet.values == 0
    assert all(r.values_read == 0 for r in quiet.results)


# --- the column each reader assigns ---


def test_ignoring_merged_cells_shifts_a_row_left():
    rows = source_rows(lxml.html.fromstring(MATRIX))
    assert columns_ignoring_spans(rows)[1] == [0, 1], "Seal lands in column 0"
    assert columns_expanding_spans(rows)[1] == [1, 2], "where it belongs"


# --- the reimplementations against the real tools ---


def test_html2text_loses_every_icon():
    html2text = pytest.importorskip("html2text")
    rendered = html2text.HTML2Text().handle(MATRIX)
    assert "Standard" in rendered
    assert "tick" not in rendered and "cross" not in rendered


def test_beautifulsoup_returns_empty_strings_for_icon_cells():
    bs4 = pytest.importorskip("bs4")
    soup = bs4.BeautifulSoup(MATRIX, "html.parser")
    row = [tr for tr in soup.find_all("tr")][2]
    cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
    assert cells == ["Standard", "", ""]


def test_pandas_gets_the_grid_right_and_still_reads_no_icon():
    """The most capable ordinary tool, and it is blind to the same thing as the others."""
    pd = pytest.importorskip("pandas")
    frame = pd.read_html(io.StringIO(MATRIX))[0]
    assert frame.shape[1] == 3, "the geometry is correct"
    values = [str(v) for v in frame.iloc[0].tolist()]
    assert values[0] == "Standard"
    assert all(v == "nan" for v in values[1:]), "and every icon is missing"
