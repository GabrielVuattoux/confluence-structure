"""Status icons, read as state and nothing more.

Confluence's status icons — the ticks, crosses and warning marks people drop into tables —
are the clearest example of what a text-only read destroys. The tag is empty, so every bit
of its meaning sits in an attribute::

    <ac:emoticon ac:name="tick"/>

Extract the text of that cell and you get an empty string. The cell looked full on screen
and comes back blank, with nothing to signal that anything was lost.

There is a second encoding, and missing it is easy. An author who pastes an icon rather
than inserting one produces an inline image pointing at the same icon set::

    <ac:image ac:alt="(error)"><ri:url ri:value=".../images/icons/emoticons/error.svg"/></ac:image>

Both are read here. What is *not* done is interpretation: this module reports that a cell
holds ``warning``, never what ``warning`` is supposed to mean in that table. Icon vocabulary
is a Confluence convention; the business meaning behind it belongs to whoever wrote the
page, and inventing it is how a reader ends up confidently wrong.

For the same reason names that merely look alike are kept apart. ``cross`` and ``error``
render identically in many themes, as do ``tick`` and ``check``; treating them as one is an
assumption about rendering, not a fact in the file. Where a page labels its own icon —
``ac:alt="(tick)"`` on an image — that label is read, because reading an attribute is not
assuming anything.
"""

from __future__ import annotations

from typing import Literal

from lxml.html import HtmlElement
from pydantic import BaseModel

EMOTICON_TAG = "ac:emoticon"
IMAGE_TAG = "ac:image"
URL_TAG = "ri:url"

#: Path fragment marking an ``<ac:image>`` as a status icon rather than page content.
ICON_URL_MARKER = "/icons/emoticons/"

#: Confluence's built-in emoticon vocabulary. A name outside it is reported unknown rather
#: than guessed at, so the caller can decide whether to trust the page.
KNOWN_EMOTICON_NAMES = frozenset(
    {
        "smile", "sad", "cheeky", "laugh", "wink",
        "thumbs-up", "thumbs-down",
        "information", "tick", "cross", "warning",
        "plus", "minus", "question",
        "light-on", "light-off",
        "yellow-star", "red-star", "green-star", "blue-star",
    }
)  # fmt: skip

#: Icon names that appear in the image encoding, taken from Confluence's own icon files.
KNOWN_IMAGE_ICON_NAMES = frozenset({"error", "check", "warning", "information", "tick"})

Encoding = Literal["emoticon", "emoji", "image"]


class Icon(BaseModel):
    """One status icon, as the markup spells it.

    Attributes:
        name: The state as written — ``tick``, ``warning``, ``error``. Never translated.
        encoding: Which form carried it. ``emoji`` covers the newer emoticons that carry a
            unicode codepoint instead of a Confluence name.
        raw: The attribute value the name came from, kept so a reading can be audited.
        known: Whether ``name`` belongs to the recognised vocabulary.

    """

    name: str
    encoding: Encoding
    raw: str
    known: bool


def is_known(name: str, encoding: Encoding) -> bool:
    """Return whether ``name`` belongs to the recognised vocabulary for ``encoding``.

    Emoji emoticons carry an explicit codepoint, so they describe themselves and are always
    accepted.
    """
    if encoding == "emoji":
        return True
    if encoding == "image":
        return name in KNOWN_IMAGE_ICON_NAMES
    return name in KNOWN_EMOTICON_NAMES


def _from_emoticon(element: HtmlElement) -> Icon | None:
    """Build an icon from an ``<ac:emoticon>`` element."""
    name = element.get("ac:name")
    if name is None:
        return None
    encoding: Encoding = "emoji" if element.get("ac:emoji-id") else "emoticon"
    return Icon(name=name, encoding=encoding, raw=name, known=is_known(name, encoding))


def _from_image(element: HtmlElement) -> Icon | None:
    """Build an icon from an ``<ac:image>`` pointing at the icon set.

    The name comes from ``ac:alt`` when the page provides one, and from the file stem
    otherwise. Content images — a diagram, a screenshot — are not icons and return ``None``.
    """
    url = next((u.get("ri:value") for u in element.iter(URL_TAG) if u.get("ri:value")), None)
    if url is None or ICON_URL_MARKER not in url:
        return None
    stem = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    alt = (element.get("ac:alt") or "").strip()
    name = alt[1:-1] if alt.startswith("(") and alt.endswith(")") else stem
    return Icon(name=name, encoding="image", raw=alt or url, known=is_known(name, "image"))


def icons_in(element: HtmlElement) -> list[Icon]:
    """Return every status icon inside ``element``, in document order.

    Both encodings are collected. Images that are not part of the icon set are ignored, so
    a page's diagrams do not arrive disguised as states.
    """
    found: list[Icon] = []
    for node in element.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag == EMOTICON_TAG:
            icon = _from_emoticon(node)
        elif node.tag == IMAGE_TAG:
            icon = _from_image(node)
        else:
            continue
        if icon is not None:
            found.append(icon)
    return found
