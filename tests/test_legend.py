import lxml.html
import pytest

from confluence_structure.legend import extract_legend
from confluence_structure.parser import parse_html

LEGEND = (
    "<p><strong>Legend:</strong>"
    ' <ac:emoticon ac:name="tick" /> always required'
    ' <ac:emoticon ac:name="warning" /> required above 500 kg'
    ' <ac:emoticon ac:name="cross" /> not applicable here</p>'
)


def legend_of(markup: str):
    return extract_legend(lxml.html.fromstring(f"<div>{markup}</div>"))


def test_a_page_can_declare_what_its_icons_mean():
    legend = legend_of(LEGEND)
    assert {e.icon: e.meaning for e in legend.entries} == {
        "tick": "always required",
        "warning": "required above 500 kg",
        "cross": "not applicable here",
    }


def test_a_declared_meaning_reaches_the_value():
    """The point of reading a legend: report what a state means, not what it is called."""
    page = parse_html(
        LEGEND + '<table><tbody><tr><th>Check</th></tr>'
        '<tr><td><ac:emoticon ac:name="warning" /></td></tr></tbody></table>'
    )
    cell = page.tables[0].body_rows()[0][0]
    assert page.legend is not None
    assert page.legend.meaning_of(cell.icons[0].name) == "required above 500 kg"


def test_a_lone_icon_in_a_sentence_is_not_a_legend():
    """That is prose that happens to contain a symbol."""
    assert legend_of('<p><ac:emoticon ac:name="tick" /> the check passed</p>').is_empty


def test_icons_inside_a_table_are_values_not_declarations():
    """Letting them through would read a grid as a statement about icons."""
    markup = (
        "<table><tbody><tr>"
        '<td><ac:emoticon ac:name="tick" /> always required</td>'
        '<td><ac:emoticon ac:name="cross" /> never required</td>'
        "</tr></tbody></table>"
    )
    assert legend_of(markup).is_empty


def test_a_footnote_marker_is_not_a_meaning():
    markup = (
        '<p><ac:emoticon ac:name="tick" /> 1 <ac:emoticon ac:name="cross" /> 2</p>'
    )
    assert legend_of(markup).is_empty


def test_a_meaning_longer_than_a_label_is_prose():
    long_phrase = "required whenever the shipment exceeds the declared mass by any margin"
    markup = (
        f'<p><ac:emoticon ac:name="tick" /> {long_phrase}'
        f' <ac:emoticon ac:name="cross" /> {long_phrase}</p>'
    )
    assert legend_of(markup).is_empty


def test_two_legends_that_disagree_cancel_each_other():
    """Picking a side would invent a meaning the page never gave."""
    legend = legend_of(
        '<p><ac:emoticon ac:name="tick" /> always required'
        ' <ac:emoticon ac:name="cross" /> not applicable</p>'
        '<p><ac:emoticon ac:name="tick" /> under review'
        ' <ac:emoticon ac:name="warning" /> partial</p>'
    )
    assert legend.conflicts["tick"] == ["always required", "under review"]
    assert legend.meaning_of("tick") is None
    assert legend.meaning_of("cross") == "not applicable"


def test_a_page_without_a_legend_leaves_states_unread():
    page = parse_html(
        '<table><tbody><tr><th>Check</th></tr>'
        '<tr><td><ac:emoticon ac:name="warning" /></td></tr></tbody></table>'
    )
    assert page.legend is not None and page.legend.is_empty
    assert page.legend.meaning_of("warning") is None


def test_an_icon_the_legend_does_not_mention_has_no_meaning():
    assert legend_of(LEGEND).meaning_of("light-off") is None


@pytest.mark.parametrize("count", [0, 1])
def test_fewer_than_two_entries_is_not_a_legend(count):
    markup = "".join(
        '<p><ac:emoticon ac:name="tick" /> always required</p>' for _ in range(count)
    )
    assert legend_of(markup).is_empty
