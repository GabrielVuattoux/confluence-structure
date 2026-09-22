"""Table geometry, expanded so a value cannot drift away from its column.

An HTML table is not a grid. A cell may declare ``colspan`` or ``rowspan`` and occupy
several positions, and every later cell in that row shifts to make room. Read the cells of
a row in order and assign them to columns 0, 1, 2 … and the values slide out from under
their headers.

That failure is quieter than a missing value, and worse. A blank cell makes an answer look
incomplete, which someone notices. A cell read correctly but filed under the wrong column
makes an answer look complete and be wrong about *which* thing it describes, and nobody
notices at all.

So the table is expanded into a dense ``rows × columns`` matrix. A merged cell fills every
position it covers, and the copies are marked, which keeps two things true at once: a
lookup by column always lands on the right value, and anything countable is still counted
once.

Two invariants are then checked, and a failure is reported rather than repaired:

* every row covers every column — a row that does not means the geometry is ambiguous, and
  a guess about where the gap belongs is exactly the silent error this module exists to
  prevent;
* every cell resolves to text, to a known icon state, or to nothing.

A table that fails either is flagged. The caller decides whether to use it; this module
will not quietly produce a plausible grid from an implausible one.
"""

from __future__ import annotations

from typing import Literal

from lxml.html import HtmlElement
from pydantic import BaseModel, Field

from confluence_structure.icons import Icon, icons_in

CELL_TAGS = ("td", "th")

Severity = Literal["blocking", "note"]


class Problem(BaseModel):
    """Something the reader could not resolve with certainty.

    ``blocking`` means the table should not be trusted until a person has looked at it.
    ``note`` records a fact a caller may want without casting doubt on the table.
    """

    code: str
    severity: Severity
    detail: str
    row: int | None = None


class Cell(BaseModel):
    """One position in the expanded grid.

    A merged cell's value is repeated across every position it covers; ``spanned`` marks
    the copies. Filling those positions *and* labelling them is what lets a lookup by
    column be correct while a count stays honest.
    """

    row: int
    col: int
    text: str = ""
    icons: list[Icon] = Field(default_factory=list)
    is_header: bool = False
    spanned: bool = False

    @property
    def is_empty(self) -> bool:
        """Whether the position carries neither text nor an icon."""
        return not self.text and not self.icons


class Table(BaseModel):
    """A table expanded to a dense grid."""

    index: int = 0
    n_rows: int = 0
    n_cols: int = 0
    header_rows: int = 0
    grid: list[list[Cell]] = Field(default_factory=list)
    problems: list[Problem] = Field(default_factory=list)

    @property
    def trustworthy(self) -> bool:
        """Whether the geometry resolved cleanly enough to read values from."""
        return not any(p.severity == "blocking" for p in self.problems)

    def column_labels(self) -> list[str]:
        """Return one label per column, joined down the header rows.

        A header merged down several rows repeats its text, so consecutive duplicates are
        collapsed: a row-spanned "Region" stays ``"Region"``, while a column-spanned group
        above a sub-header becomes ``"Alerts Session"``.
        """
        if not self.header_rows:
            return []
        labels: list[str] = []
        for col in range(self.n_cols):
            parts: list[str] = []
            for row in range(self.header_rows):
                text = self.grid[row][col].text
                if text and (not parts or parts[-1] != text):
                    parts.append(text)
            labels.append(" ".join(parts))
        return labels

    def body_rows(self) -> list[list[Cell]]:
        """Return the rows below the header."""
        return self.grid[self.header_rows :]


def _span(element: HtmlElement, attribute: str) -> int:
    """Read a span attribute, defaulting to 1 when absent or unusable."""
    raw = element.get(attribute)
    if raw is None:
        return 1
    try:
        value = int(raw)
    except ValueError:
        return 1
    return value if value > 0 else 1


def _cell_text(element: HtmlElement) -> str:
    """Return a cell's own text.

    A nested table is a table in its own right, so its contents are left out rather than
    folded into the parent cell, which would corrupt both. A line break counts as a space:
    without that, "Product<br/>Risk" arrives as "ProductRisk".
    """
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        tag = child.tag if isinstance(child.tag, str) else ""
        if tag == "table":
            if child.tail:
                parts.append(child.tail)
            continue
        if tag == "br":
            parts.append(" ")
        parts.append(_cell_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join("".join(parts).split())


def _own_rows(table: HtmlElement) -> list[HtmlElement]:
    """Return the ``<tr>`` elements belonging to this table, not to a nested one."""
    return [tr for tr in table.iter("tr") if next(tr.iterancestors("table"), None) is table]


def build_table(element: HtmlElement, index: int = 0) -> Table:
    """Expand one ``<table>`` element into a dense grid.

    Args:
        element: The table element.
        index: Its position within the page, so a problem can be located.

    Returns:
        The expanded table, carrying any problems found while building it.

    """
    problems: list[Problem] = []
    occupied: dict[tuple[int, int], Cell] = {}

    for row_index, tr in enumerate(_own_rows(element)):
        col = 0
        for cell_element in tr:
            tag = cell_element.tag if isinstance(cell_element.tag, str) else ""
            if tag not in CELL_TAGS:
                continue
            while (row_index, col) in occupied:
                col += 1
            colspan = _span(cell_element, "colspan")
            rowspan = _span(cell_element, "rowspan")
            text = _cell_text(cell_element)
            icons = icons_in(cell_element)
            is_header = tag == "th"

            for down in range(rowspan):
                for across in range(colspan):
                    occupied[(row_index + down, col + across)] = Cell(
                        row=row_index + down,
                        col=col + across,
                        text=text,
                        icons=icons,
                        is_header=is_header,
                        spanned=not (down == 0 and across == 0),
                    )

            for icon in icons:
                if not icon.known:
                    problems.append(
                        Problem(
                            code="unknown_icon",
                            severity="blocking",
                            detail=f"unrecognised icon name {icon.name!r} ({icon.encoding})",
                            row=row_index,
                        )
                    )
            col += colspan

    n_rows = max((r for r, _ in occupied), default=-1) + 1
    n_cols = max((c for _, c in occupied), default=-1) + 1
    grid = [
        [occupied.get((r, c), Cell(row=r, col=c)) for c in range(n_cols)] for r in range(n_rows)
    ]

    header_rows = 0
    for row in grid:
        if row and all(cell.is_header for cell in row):
            header_rows += 1
        else:
            break

    for r in range(n_rows):
        covered = sum(1 for c in range(n_cols) if (r, c) in occupied)
        if covered != n_cols:
            problems.append(
                Problem(
                    code="incomplete_row",
                    severity="blocking",
                    detail=f"row covers {covered} of {n_cols} columns",
                    row=r,
                )
            )

    if any(nested is not element for nested in element.iter("table")):
        problems.append(
            Problem(
                code="nested_table",
                severity="note",
                detail="a cell contains a table of its own; its content is not folded in",
            )
        )

    if n_rows and not header_rows:
        problems.append(
            Problem(
                code="no_header_row",
                severity="note",
                detail="no <th> row: column labels are implied by layout, not declared",
            )
        )

    return Table(
        index=index,
        n_rows=n_rows,
        n_cols=n_cols,
        header_rows=header_rows,
        grid=grid,
        problems=problems,
    )
