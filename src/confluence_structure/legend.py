"""The meaning a page gives its own icons.

Reading ``ac:name="warning"`` off a tag is certain. Knowing what ``warning`` is *supposed to
mean in that table* is not — icon vocabulary is a Confluence convention, and the meaning
behind it belongs to whoever wrote the page.

Except when the page says. Authors who build a table out of icons routinely explain them
just above it::

    Legend:  ✓ required on every shipment   ⚠ required above 500 kg   ✗ not applicable here

When that paragraph exists, the mapping is a lookup rather than a guess, and a value can be
reported as *what it means* instead of *what it is called*. When it does not exist, the
state travels unread, which is the honest alternative.

A legend is recognised by shape, not by the word "legend", because the word is not always
there and is not always English. What identifies one is a run of at least
:data:`MIN_ENTRIES` icons, each followed by a short phrase, outside any table. Three things
are deliberately excluded:

* icons **inside** a table — those are values in a grid, not statements about icons;
* a lone icon in a sentence, which is prose that happens to contain a symbol;
* a "meaning" with no letters in it, which is a footnote marker rather than a definition.

Where a page carries two legends that disagree about the same icon, neither is applied.
Merging them would invent a meaning the page never gave.
"""

from __future__ import annotations

from collections import defaultdict

from lxml.html import HtmlElement
from pydantic import BaseModel, Field

from confluence_structure.icons import EMOTICON_TAG, IMAGE_TAG, icons_in

#: One icon followed by text is a sentence. A legend is a run of them.
MIN_ENTRIES = 2

#: A meaning is a label, not a paragraph. Anything longer is prose that follows an icon.
MAX_MEANING_CHARS = 60

#: Enough letters to be a definition rather than a footnote marker such as "1" or "2".
MIN_MEANING_LETTERS = 3


class LegendEntry(BaseModel):
    """One icon and the meaning its page gives it."""

    icon: str
    meaning: str


class Legend(BaseModel):
    """The icon vocabulary a page declares for itself."""

    entries: list[LegendEntry] = Field(default_factory=list)
    conflicts: dict[str, list[str]] = Field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Whether the page declared nothing usable."""
        return not self.entries

    def meaning_of(self, icon: str) -> str | None:
        """Return the meaning this page gives ``icon``, or ``None``.

        An icon caught in a conflict has no meaning here: the page contradicts itself, and
        picking a side would be inventing one.
        """
        if icon in self.conflicts:
            return None
        return next((entry.meaning for entry in self.entries if entry.icon == icon), None)


def _meaning_after(node: HtmlElement) -> str:
    """Return the text following ``node`` up to the next icon, within its parent."""
    parts: list[str] = [node.tail or ""]
    for sibling in node.itersiblings():
        tag = sibling.tag if isinstance(sibling.tag, str) else ""
        if tag in (EMOTICON_TAG, IMAGE_TAG) or icons_in(sibling):
            break
        parts.append(sibling.text_content() or "")
        parts.append(sibling.tail or "")
    return " ".join(" ".join(parts).split())


def _is_definition(meaning: str) -> bool:
    """Whether a phrase reads as a definition rather than a reference mark."""
    letters = sum(1 for character in meaning if character.isalpha())
    return bool(meaning) and len(meaning) <= MAX_MEANING_CHARS and letters >= MIN_MEANING_LETTERS


def extract_legend(root: HtmlElement) -> Legend:
    """Read the icon legend a page declares, if it declares one.

    Args:
        root: The parsed page.

    Returns:
        The legend, empty when the page declares none.

    """
    declared: dict[str, list[str]] = defaultdict(list)

    for container in root.iter():
        if not isinstance(container.tag, str) or container.tag == "table":
            continue
        if next(container.iterancestors("table"), None) is not None:
            continue

        run: list[tuple[str, str]] = []
        for node in container.iter():
            tag = node.tag if isinstance(node.tag, str) else ""
            if tag not in (EMOTICON_TAG, IMAGE_TAG):
                continue
            if next(node.iterancestors("table"), None) is not None:
                continue
            icons = icons_in(node)
            meaning = _meaning_after(node)
            if icons and _is_definition(meaning):
                run.append((icons[0].name, meaning))

        if len(run) >= MIN_ENTRIES:
            for icon, meaning in run:
                if meaning not in declared[icon]:
                    declared[icon].append(meaning)

    return Legend(
        entries=[
            LegendEntry(icon=icon, meaning=meanings[0])
            for icon, meanings in sorted(declared.items())
            if len(meanings) == 1
        ],
        conflicts={icon: meanings for icon, meanings in declared.items() if len(meanings) > 1},
    )
