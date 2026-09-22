from pathlib import Path

from confluence_structure.parser import parse_file, parse_html

PAGE = """
<h1>Overview</h1><p>The short version.</p>
<h2>Process</h2><p>See the diagram.</p>
<svg><text>Start</text><text>Approve</text></svg>
<table><tbody>
  <tr><th>Step</th><th>Required</th></tr>
  <tr><td>Collect</td><td><ac:emoticon ac:name="tick" /></td></tr>
</tbody></table>
<p><ac:link ac:anchor="top"><ri:page ri:content-title="Other Page" /></ac:link>
   <a href="https://example.org/doc">outside</a></p>
<ac:structured-macro ac:name="view-file">
  <ac:parameter ac:name="name"><ri:attachment ri:filename="rates.xlsx" /></ac:parameter>
</ac:structured-macro>
<ac:structured-macro ac:name="children" />
<ac:structured-macro ac:name="info"><ac:rich-text-body><p>kept</p></ac:rich-text-body>
</ac:structured-macro>
"""


# --- sections ---


def test_prose_is_split_at_its_headings():
    page = parse_html(PAGE)
    assert [(s.level, s.heading) for s in page.sections] == [(1, "Overview"), (2, "Process")]


def test_a_heading_names_its_section_without_joining_the_text():
    page = parse_html(PAGE)
    overview = next(s for s in page.sections if s.heading == "Overview")
    assert overview.text == "The short version."


def test_a_page_without_headings_yields_one_unnamed_section():
    (section,) = parse_html("<p>Just prose.</p>").sections
    assert section.heading == "" and section.text == "Just prose."


def test_readable_figure_text_joins_the_section_it_sits_in():
    """On a page whose process is a diagram, that text is the only content there is."""
    process = next(s for s in parse_html(PAGE).sections if s.heading == "Process")
    assert "[figure]" in process.text and "Approve" in process.text


def test_an_unreadable_figure_adds_nothing_to_its_section():
    markup = (
        "<h2>Process</h2><p>See it.</p>"
        '<ac:image><ri:attachment ri:filename="f.png" /></ac:image>'
    )
    section = next(s for s in parse_html(markup).sections if s.heading == "Process")
    assert "[figure]" not in section.text


def test_table_contents_do_not_leak_into_the_prose():
    """Tables travel structurally; flattening them here would undo the reading."""
    assert "Collect" not in " ".join(s.text for s in parse_html(PAGE).sections)


# --- page text ---


def test_macro_configuration_is_not_page_text():
    """Otherwise a page's prose ends up seasoned with `false` and `none`."""
    markup = (
        '<p>Real words.</p><ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="border">false</ac:parameter></ac:structured-macro>'
    )
    assert parse_html(markup).text == "Real words."


# --- references, attachments, macros ---


def test_a_page_reference_keeps_its_title_verbatim():
    """Nothing in an export maps a title to a file, so the title is what we can honestly keep."""
    page = parse_html(PAGE)
    (reference,) = [r for r in page.references if r.kind == "page"]
    assert (reference.target, reference.anchor) == ("Other Page", "top")


def test_external_links_are_kept_separately():
    page = parse_html(PAGE)
    assert [r.target for r in page.references if r.kind == "external"] == ["https://example.org/doc"]


def test_attachments_are_collected_with_how_they_were_referenced():
    page = parse_html(PAGE)
    assert {(a.filename, a.via) for a in page.attachments} == {("rates.xlsx", "view-file")}


def test_a_macro_that_builds_its_body_at_render_time_is_marked():
    """A page made of these looks nearly empty in the export; reading it as empty is wrong."""
    page = parse_html(PAGE)
    marked = {m.name: m.generates_content for m in page.macros}
    assert marked["children"] is True
    assert marked["info"] is False


# --- the page as a whole ---


def test_a_table_is_read_through_the_page():
    page = parse_html(PAGE)
    assert len(page.tables) == 1
    assert page.icon_count == 1
    assert page.trustworthy


def test_a_page_is_untrustworthy_when_one_of_its_tables_is():
    ragged = "<table><tbody><tr><th>A</th><th>B</th></tr><tr><td>1</td></tr></tbody></table>"
    page = parse_html(ragged)
    assert not page.trustworthy


def test_unreadable_figures_can_be_listed():
    page = parse_html(PAGE + '<ac:image><ri:attachment ri:filename="chart.png" /></ac:image>')
    assert [f.source for f in page.unreadable_figures()] == ["chart.png"]


def test_a_merged_cell_is_counted_once():
    page = parse_html(
        '<table><tbody><tr><th>A</th><th>B</th></tr>'
        '<tr><td colspan="2"><ac:emoticon ac:name="tick" /></td></tr></tbody></table>'
    )
    assert page.icon_count == 1


def test_the_page_id_comes_from_the_file_name(tmp_path: Path):
    path = tmp_path / "123456.html"
    path.write_text(PAGE, encoding="utf-8")
    page = parse_file(path)
    assert page.page_id == "123456"
    assert page.source == str(path)
