"""What one page amounts to once it has been read.

The shape here is deliberately plain: a page is its sections, its tables, the things it
points at, and the macros it uses. Everything a caller might want to check later —
which figure could not be read, which macro generates content that is not in the file —
is carried rather than summarised away.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from confluence_structure.figures import Figure
from confluence_structure.grid import Table

ReferenceKind = Literal["page", "external"]
AttachmentVia = Literal["image", "view-file", "link"]

#: Macros whose body does not exist in the storage format: they are rendered from a query
#: at display time. A page built out of these looks nearly empty in the export, and reading
#: it as empty is a mistake worth catching.
GENERATED_MACROS = frozenset(
    {"children", "pagetree", "contentbylabel", "toc", "detailssummary", "excerpt-include"}
)


class Section(BaseModel):
    """A run of prose under one heading.

    Kept separate so a quotation can say where on the page it came from. Tables are not
    folded in — they travel structurally, and flattening them here would undo the reading.
    """

    heading: str = ""
    level: int = 0
    text: str = ""


class Reference(BaseModel):
    """Something the page points at.

    A Confluence page link names its target by **title**, while an export names its files
    by page id. Nothing in the export bridges the two, so resolving these needs the index
    that usually ships alongside — which is why the title is kept verbatim rather than
    turned into a path that might be wrong.
    """

    kind: ReferenceKind
    target: str
    anchor: str | None = None


class Attachment(BaseModel):
    """A file the page depends on."""

    filename: str
    via: AttachmentVia


class Macro(BaseModel):
    """A macro call.

    ``generates_content`` marks the ones whose body is produced at render time, so a caller
    can tell a genuinely short page from one whose content simply is not in the file.
    """

    name: str
    generates_content: bool


class Page(BaseModel):
    """One parsed page."""

    page_id: str = ""
    source: str = ""
    text: str = ""
    sections: list[Section] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    figures: list[Figure] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    macros: list[Macro] = Field(default_factory=list)

    @property
    def trustworthy(self) -> bool:
        """Whether every table on the page resolved cleanly."""
        return all(table.trustworthy for table in self.tables)

    @property
    def icon_count(self) -> int:
        """Status icons across the page's tables, counting a merged cell once."""
        return sum(
            len(cell.icons)
            for table in self.tables
            for row in table.grid
            for cell in row
            if not cell.spanned
        )

    def unreadable_figures(self) -> list[Figure]:
        """Return the figures whose content is somewhere this reader cannot follow."""
        return [figure for figure in self.figures if not figure.readable]
