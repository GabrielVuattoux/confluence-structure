import base64

import lxml.html
import pytest

from confluence_structure.figures import figure_of, figures_in, text_from_svg

SVG = '<svg><text x="1">Start</text><text>Decision</text><text>   </text></svg>'


def parse(fragment: str):
    return lxml.html.fromstring(f"<div>{fragment}</div>")


def test_an_svg_keeps_its_labels_as_text():
    """A drawing stored as SVG needs no vision model: its labels are text nodes."""
    assert text_from_svg(SVG) == "Start · Decision"


def test_an_inline_svg_is_readable():
    (figure,) = figures_in(parse(SVG))
    assert figure.kind == "inline_svg"
    assert figure.readable and "Decision" in figure.text


def test_a_percent_encoded_data_uri_is_decoded():
    encoded = "data:image/svg+xml,%3Csvg%3E%3Ctext%3EReview%3C/text%3E%3C/svg%3E"
    (figure,) = figures_in(parse(f'<img src="{encoded}" alt="approval flow">'))
    assert figure.kind == "data_uri_svg"
    assert figure.text == "Review" and figure.alt == "approval flow"
    assert figure.source == "", "an embedded drawing points at no file"


def test_a_base64_data_uri_is_decoded():
    payload = base64.b64encode(b"<svg><text>Escalate</text></svg>").decode()
    (figure,) = figures_in(parse(f'<img src="data:image/svg+xml;base64,{payload}">'))
    assert figure.text == "Escalate"


def test_a_malformed_data_uri_yields_nothing_rather_than_raising():
    (figure,) = figures_in(parse('<img src="data:image/svg+xml;base64,not-base64!!">'))
    assert figure.text == "" and not figure.readable


def test_alternative_text_alone_makes_a_figure_readable():
    markup = (
        '<ac:image ac:alt="Order placement process">'
        '<ri:attachment ri:filename="flow.png" /></ac:image>'
    )
    (figure,) = figures_in(parse(markup))
    assert figure.readable and figure.alt == "Order placement process"
    assert figure.source == "flow.png"


def test_alternative_text_that_is_only_a_file_name_is_discarded():
    """`alt="image-2025-3-28.png"` describes nothing, and counting it would mislead."""
    markup = (
        '<ac:image ac:alt="image-2025-3-28.png">'
        '<ri:attachment ri:filename="x.png" /></ac:image>'
    )
    (figure,) = figures_in(parse(markup))
    assert figure.alt == "" and not figure.readable


def test_a_plain_attachment_is_unreadable_not_mis_parsed():
    """The content is in another file. That is a delivery fact, not a parsing failure."""
    (figure,) = figures_in(parse('<ac:image><ri:attachment ri:filename="flow.png" /></ac:image>'))
    assert figure.kind == "attachment" and not figure.readable


def test_a_drawio_macro_holds_a_name_not_a_drawing():
    """It looks like structured content and yields nothing but a label."""
    markup = (
        '<ac:structured-macro ac:name="drawio">'
        '<ac:parameter ac:name="diagramName">Approval</ac:parameter></ac:structured-macro>'
    )
    (figure,) = figures_in(parse(markup))
    assert figure.kind == "drawio" and figure.source == "Approval" and not figure.readable


def test_status_icons_are_not_figures():
    """Letting one through would turn a table's contents into decoration."""
    icon = '<ac:image><ri:url ri:value="https://w/_/images/icons/emoticons/error.svg" /></ac:image>'
    assert figures_in(parse(icon)) == []
    assert figure_of(parse(icon)[0]) is None


@pytest.mark.parametrize("markup", ["<svg></svg>", "<svg><text>   </text></svg>"])
def test_an_svg_without_labels_is_not_readable(markup):
    (figure,) = figures_in(parse(markup))
    assert not figure.readable
