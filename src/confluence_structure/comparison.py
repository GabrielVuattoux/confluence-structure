"""Measure what a text-only read costs, against a corpus rather than in the abstract.

The claim behind this library — that reading a Confluence export as text destroys
information — is a measurable one, so it is measured instead of asserted.

Three baselines stand for what someone would reach for, in ascending order of care:

``TEXT_ONLY``
    Strip the markup and keep the text. ``html2text``, or ``BeautifulSoup.get_text()``.

``TABLE_TEXT``
    Walk the tables and read each cell as text, taking a row's cells in order. The
    hand-rolled approach, and the most common one.

``TABLE_TEXT_SPANS``
    The same, but expanding ``colspan`` and ``rowspan`` so values keep their column. What
    ``pandas.read_html`` does, and the best of the ordinary tools.

They are reimplemented here so the measurement needs no extra dependency at runtime. Tests
run the real tools where installed and check both halves of that substitution: that each
tool loses what the baseline says it loses, and that the span-expanding baseline puts a
value in the same column pandas does. A baseline that landed somewhere else would be
measuring the wrong thing.

Two costs, and they fail differently:

**Lost.** A cell whose only content is an icon is empty to every text-based reader. The
answer is visibly incomplete — awkward, but someone notices.

**Misplaced.** A reader that ignores merged cells shifts a row's values away from their
headers. The answer looks complete and describes the wrong thing. Nobody notices.

A value counts as usable only if it was read *and* landed under the column it belongs to.
Both halves are required: a value read correctly and filed under the wrong heading is not a
partial success.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import lxml.html
from lxml.html import HtmlElement
from pydantic import BaseModel, Field

from confluence_structure.icons import icons_in
from confluence_structure.parser import parse_file

Approach = Literal["TEXT_ONLY", "TABLE_TEXT", "TABLE_TEXT_SPANS", "ATTRIBUTE_AWARE"]

APPROACH_LABELS: dict[Approach, str] = {
    "TEXT_ONLY": "text only (html2text, get_text)",
    "TABLE_TEXT": "tables, text cells, spans ignored",
    "TABLE_TEXT_SPANS": "tables, text cells, spans expanded",
    "ATTRIBUTE_AWARE": "attribute-aware (this library)",
}

#: One cell as the markup declares it: its text, whether an icon sits in it, and its spans.
SourceCell = tuple[str, bool, int, int]


class ApproachResult(BaseModel):
    """What one approach recovers."""

    approach: Approach
    label: str
    values_read: int = 0
    values_misplaced: int = 0
    icon_states_read: int = 0

    def usable(self, total: int) -> float:
        """Share of values read *and* placed under the right column."""
        if not total:
            return 0.0
        return round((self.values_read - self.values_misplaced) / total, 4)


class Comparison(BaseModel):
    """The measurement over a corpus."""

    pages: int = 0
    tables: int = 0
    values: int = 0
    icon_values: int = 0
    empty_cells: int = 0
    tables_with_merged_cells: int = 0
    results: list[ApproachResult] = Field(default_factory=list)

    def render(self) -> str:
        """Format the comparison for a terminal."""
        total = max(self.values, 1)
        lines = [
            f"{self.pages} pages, {self.tables} tables, {self.values} table cells with a value",
            f"  the value is an icon in {self.icon_values} of them "
            f"({self.icon_values / total:.1%})",
            f"  {self.tables_with_merged_cells} tables use merged cells",
            "",
            "Measured over table content only. Reading prose as text loses nothing; this is",
            "what happens to the pages where the answer lives in a grid.",
            "",
            f"{'approach':38} {'values':>7} {'icons':>7} {'misplaced':>10} {'usable':>8}",
        ]
        for result in self.results:
            lines.append(
                f"{result.label:38} {result.values_read:7} {result.icon_states_read:7} "
                f"{result.values_misplaced:10} {result.usable(self.values):8.1%}"
            )
        return "\n".join(lines)


def _span(element: HtmlElement, name: str) -> int:
    """Read a span attribute, defaulting to 1."""
    try:
        value = int(element.get(name) or 1)
    except ValueError:
        return 1
    return value if value > 0 else 1


def source_rows(table: HtmlElement) -> list[list[SourceCell]]:
    """Describe a table exactly as its markup declares it.

    Read from the source rather than from an expanded grid: spans are attributes, and
    reading them is the only way to know what a naive reader would have seen.
    """
    rows: list[list[SourceCell]] = []
    for tr in table.iter("tr"):
        if next(tr.iterancestors("table"), None) is not table:
            continue
        row: list[SourceCell] = []
        for cell in tr:
            tag = cell.tag if isinstance(cell.tag, str) else ""
            if tag not in ("td", "th"):
                continue
            text = " ".join((cell.text_content() or "").split())
            row.append((text, bool(icons_in(cell)), _span(cell, "colspan"), _span(cell, "rowspan")))
        rows.append(row)
    return rows


def columns_ignoring_spans(rows: list[list[SourceCell]]) -> list[list[int]]:
    """Column each cell gets from a reader that numbers a row's cells in order."""
    return [list(range(len(row))) for row in rows]


def columns_expanding_spans(rows: list[list[SourceCell]]) -> list[list[int]]:
    """Column each cell gets from a reader that expands merged cells, as pandas does."""
    occupied: set[tuple[int, int]] = set()
    assigned: list[list[int]] = []
    for r, row in enumerate(rows):
        columns: list[int] = []
        col = 0
        for _text, _icon, colspan, rowspan in row:
            while (r, col) in occupied:
                col += 1
            columns.append(col)
            for down in range(rowspan):
                for across in range(colspan):
                    occupied.add((r + down, col + across))
            col += colspan
        assigned.append(columns)
    return assigned


def compare(pages: list[Path]) -> Comparison:
    """Measure every approach over a corpus.

    Args:
        pages: The storage-format files to read.

    Returns:
        The comparison. Figures come from this library's own reading, so they move when it
        does — which is the point of committing the corpus beside it.

    """
    report = Comparison(pages=len(pages))
    read = dict.fromkeys(APPROACH_LABELS, 0)
    misplaced = dict.fromkeys(APPROACH_LABELS, 0)
    icons = dict.fromkeys(APPROACH_LABELS, 0)

    for path in pages:
        page = parse_file(path)
        report.tables += len(page.tables)
        root = lxml.html.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        elements = [t for t in root.iter("table") if next(t.iterancestors("table"), None) is None]

        for table, element in zip(page.tables, elements, strict=True):
            rows = source_rows(element)
            naive = columns_ignoring_spans(rows)
            expanded = columns_expanding_spans(rows)
            declared_columns = [
                [cell.col for cell in table.grid[r] if not cell.spanned]
                for r in range(table.n_rows)
            ]
            if any(cell.spanned for row in table.grid for cell in row):
                report.tables_with_merged_cells += 1

            for r, row in enumerate(rows):
                for index, (text, has_icon, _c, _rs) in enumerate(row):
                    if not text and not has_icon:
                        report.empty_cells += 1
                        continue
                    report.values += 1
                    if has_icon:
                        report.icon_values += 1

                    true_column = declared_columns[r][index]
                    if not text:
                        # An icon-only cell survives no text-based read at all.
                        read["ATTRIBUTE_AWARE"] += 1
                        icons["ATTRIBUTE_AWARE"] += 1
                        continue

                    # Text-only keeps the words and loses the grid, so a value never keeps
                    # its column.
                    read["TEXT_ONLY"] += 1
                    misplaced["TEXT_ONLY"] += 1
                    read["TABLE_TEXT"] += 1
                    read["TABLE_TEXT_SPANS"] += 1
                    read["ATTRIBUTE_AWARE"] += 1
                    if has_icon:
                        icons["ATTRIBUTE_AWARE"] += 1
                    if naive[r][index] != true_column:
                        misplaced["TABLE_TEXT"] += 1
                    if expanded[r][index] != true_column:
                        misplaced["TABLE_TEXT_SPANS"] += 1

    report.results = [
        ApproachResult(
            approach=approach,
            label=APPROACH_LABELS[approach],
            values_read=read[approach],
            values_misplaced=misplaced[approach],
            icon_states_read=icons[approach],
        )
        for approach in APPROACH_LABELS
    ]
    return report


def main() -> None:
    """Measure the demo corpus and print the comparison."""
    corpus = Path(__file__).resolve().parents[2] / "corpus" / "pages"
    print(compare(sorted(corpus.glob("*.html"))).render())


if __name__ == "__main__":
    main()
