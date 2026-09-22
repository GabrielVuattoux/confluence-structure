import lxml.html
import pytest

from confluence_structure.grid import build_table


def table_of(body: str):
    return build_table(lxml.html.fromstring(f"<table><tbody>{body}</tbody></table>"))


MERGED = """
<tr><th rowspan="2">Region</th><th colspan="2">Alerts</th></tr>
<tr><th>Session</th><th>Overnight</th></tr>
<tr><td>North</td>
    <td><ac:emoticon ac:name="tick" /></td>
    <td><ac:emoticon ac:name="cross" /></td></tr>
"""


# --- the shift a naive read produces ---


def test_a_naive_read_of_the_source_row_would_shift_the_values():
    """The defect this module exists to prevent, stated as a test.

    Row 1 declares two cells, but its first column is already taken by the row-spanned
    header above it. Numbering its cells 0, 1 puts "Session" under "Region".
    """
    rows = lxml.html.fromstring(f"<table><tbody>{MERGED}</tbody></table>").findall(".//tr")
    naive = [c.text_content().strip() for c in rows[1] if c.tag in ("td", "th")]
    assert naive == ["Session", "Overnight"]

    table = table_of(MERGED)
    assert [cell.text for cell in table.grid[1]] == ["Region", "Session", "Overnight"]


def test_a_merged_cell_fills_every_position_it_covers():
    table = table_of(MERGED)
    assert (table.n_rows, table.n_cols) == (3, 3)
    assert [cell.text for cell in table.grid[0]] == ["Region", "Alerts", "Alerts"]


def test_the_copies_are_marked_so_counts_stay_honest():
    table = table_of(MERGED)
    assert table.grid[0][1].spanned is False
    assert table.grid[0][2].spanned is True
    assert table.grid[1][0].spanned is True

    originals = [c for row in table.grid for c in row if not c.spanned]
    assert len(originals) == 7, "four header cells declared, plus three body cells"
    assert len([c for row in table.grid for c in row]) == 9, "but nine positions once expanded"


def test_a_value_is_reachable_by_its_column_label():
    table = table_of(MERGED)
    labels = table.column_labels()
    body = table.body_rows()[0]
    found = {labels[c.col]: (c.text or "/".join(i.name for i in c.icons)) for c in body}
    assert found == {"Region": "North", "Alerts Session": "tick", "Alerts Overnight": "cross"}


# --- labels ---


def test_a_column_spanned_group_joins_its_sub_header():
    assert table_of(MERGED).column_labels()[1] == "Alerts Session"


def test_a_row_spanned_header_is_not_repeated_into_itself():
    assert table_of(MERGED).column_labels()[0] == "Region"


def test_a_line_break_inside_a_header_becomes_a_space():
    table = table_of("<tr><th>Product<br />Risk</th></tr><tr><td>x</td></tr>")
    assert table.column_labels() == ["Product Risk"]


def test_a_table_without_a_header_row_has_no_labels():
    table = table_of("<tr><td>a</td><td>b</td></tr>")
    assert table.column_labels() == []
    assert [p.code for p in table.problems] == ["no_header_row"]
    assert table.trustworthy, "an undeclared header is worth knowing, not a reason to distrust"


# --- invariants ---


def test_a_row_that_does_not_cover_every_column_is_flagged():
    table = table_of("<tr><th>A</th><th>B</th><th>C</th></tr><tr><td>1</td><td>2</td></tr>")
    assert not table.trustworthy
    problem = next(p for p in table.problems if p.code == "incomplete_row")
    assert (problem.row, problem.severity) == (1, "blocking")
    assert "2 of 3" in problem.detail


def test_an_unknown_icon_makes_the_table_untrustworthy():
    table = table_of('<tr><th>A</th></tr><tr><td><ac:emoticon ac:name="mystery" /></td></tr>')
    assert not table.trustworthy
    assert "mystery" in next(p for p in table.problems if p.code == "unknown_icon").detail


def test_a_clean_table_reports_nothing_blocking():
    table = table_of(MERGED)
    assert table.trustworthy
    assert [p.severity for p in table.problems] == []


# --- nested tables ---


def test_a_nested_table_is_not_folded_into_its_parent_cell():
    table = table_of(
        "<tr><th>Topic</th><th>Detail</th></tr>"
        "<tr><td>one</td><td>outer<table><tbody><tr><td>inner</td></tr></tbody></table></td></tr>"
    )
    assert table.grid[1][1].text == "outer"
    assert any(p.code == "nested_table" and p.severity == "note" for p in table.problems)
    assert table.trustworthy


def test_only_the_tables_own_rows_are_counted():
    table = table_of(
        "<tr><th>A</th></tr><tr><td><table><tbody><tr><td>inner</td></tr></tbody></table></td></tr>"
    )
    assert table.n_rows == 2


# --- edges ---


@pytest.mark.parametrize("value", ["0", "-1", "abc", ""])
def test_an_unusable_span_falls_back_to_one(value):
    header = f'<tr><th colspan="{value}">A</th><th>B</th></tr>'
    table = table_of(header + "<tr><td>1</td><td>2</td></tr>")
    assert table.n_cols == 2


def test_an_empty_table_produces_an_empty_grid():
    table = build_table(lxml.html.fromstring("<table></table>"))
    assert (table.n_rows, table.n_cols) == (0, 0)
    assert table.grid == [] and table.problems == []


def test_a_gap_in_the_markup_becomes_an_empty_cell_not_a_shift():
    table = table_of('<tr><th>A</th><th>B</th></tr><tr><td>1</td><td colspan="1"></td></tr>')
    assert table.grid[1][1].is_empty
    assert table.trustworthy
