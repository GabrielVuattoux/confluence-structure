import lxml.html
import pytest

from confluence_structure.icons import (
    KNOWN_EMOTICON_NAMES,
    Icon,
    icons_in,
    is_known,
)


def parse(fragment: str) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(f"<div>{fragment}</div>")


def test_the_state_is_read_from_the_attribute():
    """The tag is empty — extract its text and the cell comes back blank."""
    markup = '<ac:emoticon ac:name="tick" />'
    assert parse(markup).text_content().strip() == ""

    (icon,) = icons_in(parse(markup))
    assert (icon.name, icon.encoding, icon.known) == ("tick", "emoticon", True)


def test_the_image_encoding_is_read_too():
    """An icon pasted rather than inserted arrives as an inline image."""
    (icon,) = icons_in(
        parse(
            '<ac:image ac:alt="(error)">'
            '<ri:url ri:value="https://w/_/images/icons/emoticons/error.svg" /></ac:image>'
        )
    )
    assert (icon.name, icon.encoding, icon.known) == ("error", "image", True)


def test_a_page_labelling_its_own_icon_is_believed():
    """`check.svg` labelled `(tick)` is the page telling us, not us assuming."""
    (icon,) = icons_in(
        parse(
            '<ac:image ac:alt="(tick)">'
            '<ri:url ri:value="https://w/_/images/icons/emoticons/check.svg" /></ac:image>'
        )
    )
    assert icon.name == "tick"


def test_an_unlabelled_image_falls_back_to_the_file_name():
    markup = (
        '<ac:image><ri:url ri:value="https://w/_/images/icons/emoticons/warning.svg" />'
        "</ac:image>"
    )
    (icon,) = icons_in(parse(markup))
    assert icon.name == "warning"


def test_a_content_image_is_not_an_icon():
    """A diagram must not arrive disguised as a state."""
    assert icons_in(parse('<ac:image><ri:attachment ri:filename="diagram.png" /></ac:image>')) == []
    assert icons_in(parse('<ac:image><ri:url ri:value="https://w/photo.png" /></ac:image>')) == []


def test_an_unrecognised_name_is_reported_not_guessed():
    (icon,) = icons_in(parse('<ac:emoticon ac:name="sparkle-of-doom" />'))
    assert icon.name == "sparkle-of-doom"
    assert icon.known is False


def test_emoji_emoticons_describe_themselves():
    """They carry a codepoint instead of a Confluence name, so there is nothing to look up."""
    (icon,) = icons_in(parse('<ac:emoticon ac:name="check mark" ac:emoji-id="2714" />'))
    assert (icon.encoding, icon.known) == ("emoji", True)


def test_names_that_look_alike_are_kept_apart():
    """cross/error and tick/check render alike; merging them assumes how a theme paints."""
    assert is_known("cross", "emoticon") and not is_known("error", "emoticon")
    assert is_known("error", "image") and is_known("check", "image")


def test_icons_come_back_in_document_order():
    markup = "".join(
        f'<ac:emoticon ac:name="{n}" />' for n in ("tick", "cross", "warning")
    )
    icons = icons_in(parse(markup))
    assert [i.name for i in icons] == ["tick", "cross", "warning"]


def test_an_emoticon_without_a_name_is_skipped():
    assert icons_in(parse("<ac:emoticon />")) == []


@pytest.mark.parametrize("name", sorted(KNOWN_EMOTICON_NAMES))
def test_every_documented_emoticon_is_recognised(name):
    (icon,) = icons_in(parse(f'<ac:emoticon ac:name="{name}" />'))
    assert icon.known, f"{name} is in the vocabulary but was not recognised"


def test_the_raw_attribute_is_kept_for_audit():
    markup = (
        '<ac:image ac:alt="(error)">'
        '<ri:url ri:value="https://w/_/images/icons/emoticons/error.svg" /></ac:image>'
    )
    (icon,) = icons_in(parse(markup))
    assert icon.raw == "(error)"
    assert isinstance(icon, Icon)
