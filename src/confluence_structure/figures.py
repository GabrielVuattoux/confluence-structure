"""Figures, and the difference between one that is unread and one that is unreadable.

A page whose process lives in a diagram is unanswerable from its prose — unless the diagram
carries its own text, which more of them do than people expect. Three cases, and they are
not equally hopeless:

**The figure is drawn as SVG.** Its labels are text nodes. Reading them needs no vision
model, no OCR, nothing but the file already in hand. This covers inline ``<svg>`` and the
``data:image/svg+xml`` form an author gets by pasting a drawing straight into a page.

**The figure has alternative text.** Written for screen readers, and frequently a better
description of a process than the paragraph next to it.

**The figure is a separate binary.** There is nothing to read: the content is in another
file. If that file came with the export, it is a job for something that can look at
pictures. If it did not, no parser recovers it, and calling that a parsing failure would be
wrong — it is a delivery problem, and the honest response is to record what is missing.

Confluence's ``drawio`` macro is the third case wearing the clothes of the first. The
storage format keeps the diagram's *name* and its display settings, never its XML, so a
macro that looks like structured content yields nothing but a label.

What this module will not do is invent. A figure it cannot read is recorded as unread.
"""

from __future__ import annotations

import base64
import binascii
import re
import urllib.parse
from typing import Literal

from lxml import etree
from lxml.html import HtmlElement
from pydantic import BaseModel

from confluence_structure.icons import ICON_URL_MARKER

SVG_TEXT = re.compile(r"<text[^>]*>(.*?)</text>", re.S)
MARKUP = re.compile(r"<[^>]+>")
DATA_URI_SVG = re.compile(r"^data:image/svg\+xml[;,]", re.I)

#: Alternative text that is only the file name describes nothing, and counting it as a
#: description makes an unreadable figure look readable.
FILENAME_AS_ALT = re.compile(r"^[\w\-. ]+\.(png|jpe?g|gif|svg|bmp|webp)$", re.I)

FigureKind = Literal["attachment", "inline_svg", "data_uri_svg", "drawio"]


class Figure(BaseModel):
    """A diagram or picture, and whatever of it could be read.

    Attributes:
        kind: How the figure reached the page.
        source: The file it points at, or the diagram's name for a drawio macro.
        alt: Author-written alternative text, empty when there is none worth keeping.
        text: Labels recovered from inside the drawing.
        readable: Whether anything at all was recovered. ``False`` means the content is
            elsewhere — not that the reader gave up.

    """

    kind: FigureKind
    source: str = ""
    alt: str = ""
    text: str = ""
    readable: bool = False


def _clean(text: str) -> str:
    """Collapse whitespace."""
    return " ".join(text.split())


def text_from_svg(markup: str) -> str:
    """Return an SVG's readable labels, in document order.

    Args:
        markup: The SVG source.

    Returns:
        The text nodes joined by " · ", or an empty string when the drawing carries none.

    """
    labels = [_clean(MARKUP.sub("", raw)) for raw in SVG_TEXT.findall(markup)]
    return " · ".join(label for label in labels if label)


def _alt_of(element: HtmlElement) -> str:
    """Return usable alternative text, discarding one that is merely the file name."""
    alt = _clean(element.get("ac:alt") or element.get("alt") or "")
    return "" if FILENAME_AS_ALT.match(alt) else alt


def _svg_from_data_uri(source: str) -> str:
    """Return the SVG markup behind a ``data:`` URI, or an empty string."""
    if not DATA_URI_SVG.match(source):
        return ""
    head, _, payload = source.partition(",")
    if ";base64" in head.lower():
        try:
            return base64.b64decode(payload).decode("utf-8", errors="replace")
        except (binascii.Error, ValueError):
            return ""
    return urllib.parse.unquote(payload)


def figure_of(element: HtmlElement) -> Figure | None:
    """Return the figure ``element`` is, or ``None`` when it is not one.

    Status icons are not figures. They are values in a grid, and letting one arrive here
    would turn a table's contents into decoration.
    """
    tag = element.tag if isinstance(element.tag, str) else ""

    if tag == "svg":
        text = text_from_svg(etree.tostring(element, encoding="unicode"))
        return Figure(kind="inline_svg", text=text, readable=bool(text))

    if tag == "img":
        source = element.get("src") or ""
        alt = _alt_of(element)
        text = text_from_svg(_svg_from_data_uri(source))
        embedded = bool(DATA_URI_SVG.match(source))
        return Figure(
            kind="data_uri_svg" if embedded else "attachment",
            source="" if embedded else source,
            alt=alt,
            text=text,
            readable=bool(text or alt),
        )

    if tag == "ac:image":
        urls = [u.get("ri:value") or "" for u in element.iter("ri:url")]
        if any(ICON_URL_MARKER in url for url in urls):
            return None
        attachment = next((a.get("ri:filename") or "" for a in element.iter("ri:attachment")), "")
        alt = _alt_of(element)
        return Figure(
            kind="attachment",
            source=attachment or next((url for url in urls if url), ""),
            alt=alt,
            readable=bool(alt),
        )

    if tag == "ac:structured-macro" and element.get("ac:name") == "drawio":
        name = next(
            (
                _clean(parameter.text_content() or "")
                for parameter in element.iter("ac:parameter")
                if parameter.get("ac:name") == "diagramName"
            ),
            "",
        )
        return Figure(kind="drawio", source=name, readable=False)

    return None


def figures_in(root: HtmlElement) -> list[Figure]:
    """Return every figure under ``root``, in document order."""
    found: list[Figure] = []
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        figure = figure_of(node)
        if figure is not None:
            found.append(figure)
    return found
