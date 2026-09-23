"""Read a whole page.

``lxml.html`` keeps Confluence's namespaced tags and attributes verbatim — ``ac:emoticon``
stays ``ac:emoticon``, and ``ac:name`` stays readable on it. That is the whole trick, and
the reason this library exists: the common alternatives throw those away before anything
else gets a chance to look.

Two parts of a page are deliberately treated as content and not as markup to skip. A
figure's readable text joins the section it sits in, because on a page whose process is a
diagram that text is the only content there is. And macro *parameters* are treated as
configuration rather than prose, so a page's text does not end up seasoned with ``false``
and ``none``.
"""

from __future__ import annotations

from pathlib import Path

import lxml.html
from lxml.html import HtmlElement

from confluence_structure.figures import figure_of, figures_in
from confluence_structure.grid import build_table
from confluence_structure.legend import extract_legend
from confluence_structure.page import (
    GENERATED_MACROS,
    Attachment,
    AttachmentVia,
    Macro,
    Page,
    Reference,
    Section,
)

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")

#: Elements whose text is machine configuration rather than page content.
NON_CONTENT_TAGS = frozenset({"ac:parameter", "ri:url", "ri:attachment", "ri:page"})


def _sections(root: HtmlElement) -> list[Section]:
    """Split the page's prose into sections at its headings.

    A heading names the section that follows it and contributes no text of its own. Tables
    are skipped. A page with no heading yields one unnamed section.
    """
    sections: list[Section] = [Section()]

    def add(text: str | None) -> None:
        cleaned = " ".join((text or "").split())
        if cleaned:
            current = sections[-1]
            current.text = f"{current.text} {cleaned}".strip()

    def walk(element: HtmlElement) -> None:
        for child in element:
            tag = child.tag if isinstance(child.tag, str) else ""
            if tag == "table" or tag in NON_CONTENT_TAGS:
                add(child.tail)
                continue
            if tag in HEADING_TAGS:
                heading = " ".join((child.text_content() or "").split())
                if heading:
                    sections.append(Section(heading=heading, level=int(tag[1])))
                add(child.tail)
                continue
            figure = figure_of(child)
            if figure is not None:
                readable = " ".join(part for part in (figure.alt, figure.text) if part)
                if readable:
                    add(f"[figure] {readable}")
                add(child.tail)
                continue
            add(child.text)
            walk(child)
            add(child.tail)

    add(root.text)
    walk(root)
    return [section for section in sections if section.text or section.heading]


def _page_text(element: HtmlElement) -> str:
    """Return the page's readable text, leaving out macro configuration."""
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        if isinstance(child.tag, str) and child.tag in NON_CONTENT_TAGS:
            if child.tail:
                parts.append(child.tail)
            continue
        parts.append(_page_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(" ".join(parts).split())


def _references(root: HtmlElement) -> list[Reference]:
    """Collect what the page points at, keeping page titles verbatim."""
    found: list[Reference] = []
    for node in root.iter("ri:page"):
        title = node.get("ri:content-title")
        if not title:
            continue
        parent = node.getparent()
        anchor = parent.get("ac:anchor") if parent is not None else None
        found.append(Reference(kind="page", target=title, anchor=anchor))
    for node in root.iter("a"):
        href = node.get("href")
        if href:
            found.append(Reference(kind="external", target=href))
    return found


def _attachments(root: HtmlElement) -> list[Attachment]:
    """Collect the files the page depends on.

    How a file is referenced changes what its absence costs. An image the page displays
    leaves a hole where content was; a file someone linked to is a detour the reader can
    still decline. Both are recorded, and told apart.
    """
    found: list[Attachment] = []
    for node in root.iter("ri:attachment"):
        filename = node.get("ri:filename")
        if not filename:
            continue
        ancestors = {a.tag for a in node.iterancestors() if isinstance(a.tag, str)}
        via: AttachmentVia = "view-file"
        if "ac:image" in ancestors:
            via = "image"
        elif "ac:link" in ancestors:
            via = "link"
        found.append(Attachment(filename=filename, via=via))
    return found


def _macros(root: HtmlElement) -> list[Macro]:
    """Collect macro calls, marking those whose body is produced at render time."""
    macros: list[Macro] = []
    for node in root.iter("ac:structured-macro"):
        name = node.get("ac:name")
        if name:
            macros.append(Macro(name=name, generates_content=name in GENERATED_MACROS))
    return macros


def parse_html(source: str, page_id: str = "", origin: str = "") -> Page:
    """Read one storage-format page.

    Args:
        source: The page markup.
        page_id: An identifier for the page; exports usually name files by page id.
        origin: Where the markup came from, kept for traceability.

    Returns:
        The page. Callers that read values out of tables should check
        :attr:`~confluence_structure.page.Page.trustworthy` first.

    """
    root = lxml.html.fromstring(source)
    top_level = [t for t in root.iter("table") if next(t.iterancestors("table"), None) is None]
    return Page(
        page_id=page_id,
        source=origin,
        text=_page_text(root),
        legend=extract_legend(root),
        sections=_sections(root),
        tables=[build_table(element, index) for index, element in enumerate(top_level)],
        figures=figures_in(root),
        references=_references(root),
        attachments=_attachments(root),
        macros=_macros(root),
    )


def parse_file(path: Path) -> Page:
    """Read a storage-format file, taking the page id from its name."""
    return parse_html(
        path.read_text(encoding="utf-8", errors="replace"),
        page_id=path.stem,
        origin=str(path),
    )
