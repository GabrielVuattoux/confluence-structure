"""Generate the demo corpus.

Every measurement this project publishes is taken on pages generated here, so the numbers
can be checked rather than believed: clone, regenerate, re-measure. That is also why the
generated pages are committed alongside this script — a change in the generator then shows
up as a diff in the corpus and in the numbers, instead of silently moving both.

The corpus is fiction. Harbourline is an invented logistics company and its warehouses,
shipment classes and checks are invented with it. What is *not* invented is the shape:
these pages reproduce the things that make a real Confluence export hard to read.

    merged cells            a value belongs to a column it does not sit in
    two icon encodings      the documented tag, and the image an author gets by pasting
    a declared legend       the page says what its own icons mean
    a configuration matrix  reference data authored as page layout
    diagrams as SVG         labels readable as text
    diagrams as binaries    labels not readable at all
    a dangling reference    a link to a page the export does not contain
    generated macros        a page whose body only exists at render time
    an authoring defect     a row that does not cover every column

Run with ``python tools/build_demo_corpus.py``. Output is deterministic: no randomness, no
timestamps, so regenerating an unchanged corpus produces no diff.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
PAGES = CORPUS / "pages"

ICON_BASE = "https://wiki.harbourline.example/s/_/images/icons/emoticons"

WAREHOUSES = [
    ("Harbour East", "HE"),
    ("Harbour West", "HW"),
    ("Inland Depot", "ID"),
    ("Cold Store", "CS"),
]

CHECKS = [
    "Seal Integrity",
    "Weight Variance",
    "Temperature Log",
    "Hazard Labelling",
    "Customs Paperwork",
    "Pallet Condition",
    "Photo Evidence",
    "Recipient Signature",
]

CLASSES = ["Standard", "Express", "Fragile", "Temperature Controlled", "Hazardous"]

#: Which icon each class/check pair gets, per warehouse. Hand-written rather than generated
#: so the corpus stays stable and a reader can check a value against the page by eye.
MATRIX = {
    "HE": [
        ["tick", "tick", "cross", "warning", "tick", "tick", "warning", "tick"],
        ["tick", "tick", "cross", "warning", "tick", "information", "warning", "tick"],
        ["tick", "warning", "cross", "cross", "tick", "tick", "tick", "tick"],
        ["tick", "tick", "tick", "warning", "tick", "information", "warning", "tick"],
        ["tick", "tick", "warning", "tick", "tick", "tick", "tick", "tick"],
    ],
    "HW": [
        ["tick", "warning", "cross", "warning", "tick", "light-off", "cross", "tick"],
        ["tick", "warning", "cross", "warning", "tick", "light-off", "cross", "tick"],
        ["tick", "warning", "cross", "cross", "tick", "tick", "warning", "tick"],
        ["tick", "warning", "tick", "warning", "tick", "light-off", "cross", "tick"],
        ["tick", "tick", "warning", "tick", "tick", "tick", "warning", "tick"],
    ],
    "ID": [
        ["warning", "warning", "cross", "light-off", "tick", "light-off", "cross", "warning"],
        ["warning", "warning", "cross", "light-off", "tick", "light-off", "cross", "warning"],
        ["warning", "information", "cross", "cross", "tick", "warning", "warning", "warning"],
        ["warning", "warning", "information", "light-off", "tick", "light-off", "cross", "warning"],
        ["tick", "tick", "warning", "tick", "tick", "warning", "warning", "tick"],
    ],
    "CS": [
        ["tick", "tick", "tick", "warning", "tick", "tick", "warning", "tick"],
        ["tick", "tick", "tick", "warning", "tick", "information", "warning", "tick"],
        ["tick", "warning", "tick", "cross", "tick", "tick", "tick", "tick"],
        ["tick", "tick", "tick", "warning", "tick", "tick", "warning", "tick"],
        ["tick", "tick", "tick", "tick", "tick", "tick", "tick", "tick"],
    ],
}

#: Pairs rendered as an inline image rather than the documented tag, the way an author who
#: pastes an icon gets one instead of inserting it.
PASTED = {("HE", 2, 3), ("HW", 0, 6), ("ID", 3, 2), ("CS", 2, 3)}

#: Confluence's icon files are not named after its emoticons. Paste a cross and the page
#: gets `error.svg`; paste a tick and it gets `check.svg`. A reader that assumes the two
#: vocabularies match will look for a name that is never there.
ICON_FILES = {
    "tick": "check",
    "cross": "error",
    "warning": "warning",
    "information": "information",
}

LEGEND = [
    ("tick", "required on every shipment"),
    ("warning", "required above 500 kg"),
    ("information", "recorded, not enforced"),
    ("cross", "not applicable here"),
    ("light-off", "advisory only"),
]


@dataclass(frozen=True)
class Page:
    """One page of the corpus."""

    page_id: str
    title: str
    body: str


def emoticon(name: str) -> str:
    """Render the documented icon form."""
    return f'<ac:emoticon ac:name="{name}" />'


def pasted_icon(name: str) -> str:
    """Render the form an author gets by pasting an icon into a cell.

    The file name is Confluence's, not the emoticon's, and the page labels the image with
    that file's name rather than the one it was pasted from.
    """
    filename = ICON_FILES[name]
    return (
        f'<ac:image ac:alt="({filename})">'
        f'<ri:url ri:value="{ICON_BASE}/{filename}.svg" /></ac:image>'
    )


def legend_block() -> str:
    """Render the paragraph where a page states what its own icons mean."""
    entries = " ".join(f"{emoticon(name)} {meaning}" for name, meaning in LEGEND)
    return f"<p><strong>Legend:</strong> {entries}</p>"


def matrix_table(code: str) -> str:
    """Render one warehouse's check configuration.

    The first two columns are merged — the class name spans the two rows that share it —
    and the check columns sit under one spanning group header. Both are the everyday
    authoring habits that move a value away from its column when a reader ignores them.
    """
    head = (
        "<tr>"
        '<th rowspan="2">Shipment Class</th>'
        '<th rowspan="2">Handling</th>'
        f'<th colspan="{len(CHECKS)}">Receiving Checks</th>'
        "</tr><tr>"
        + "".join(f"<th>{check}</th>" for check in CHECKS)
        + "</tr>"
    )
    rows = []
    for index, shipment_class in enumerate(CLASSES):
        handling = "Ambient" if index < 3 else "Controlled"
        cells = []
        for column, name in enumerate(MATRIX[code][index]):
            icon = pasted_icon(name) if (code, index, column) in PASTED else emoticon(name)
            cells.append(f"<td>{icon}</td>")
        rows.append(
            f"<tr><td><strong>{shipment_class}</strong></td>"
            f"<td>{handling}</td>{''.join(cells)}</tr>"
        )
    return f"<table><tbody>{head}{''.join(rows)}</tbody></table>"


def process_svg() -> str:
    """Render an inline diagram whose labels are text nodes, so they can be read."""
    labels = ["Arrival", "Seal check", "Weigh", "Record", "Release"]
    nodes = "".join(
        f'<rect x="{20 + i * 150}" y="40" width="130" height="60" rx="8" '
        f'fill="#eef2f7" stroke="#5b6b7f" />'
        f'<text x="{85 + i * 150}" y="76" text-anchor="middle" '
        f'font-family="sans-serif" font-size="14">{label}</text>'
        for i, label in enumerate(labels)
    )
    arrows = "".join(
        f'<line x1="{150 + i * 150}" y1="70" x2="{170 + i * 150}" y2="70" stroke="#5b6b7f" />'
        for i in range(len(labels) - 1)
    )
    return f'<svg viewBox="0 0 790 140" xmlns="http://www.w3.org/2000/svg">{nodes}{arrows}</svg>'


def link_to(title: str, anchor: str | None = None) -> str:
    """Render a Confluence page link, which names its target by title."""
    attribute = f' ac:anchor="{anchor}"' if anchor else ""
    return f'<ac:link{attribute}><ri:page ri:content-title="{title}" /></ac:link>'


def build_pages() -> list[Page]:
    """Compose the corpus. Page ids are assigned in order and stay stable."""
    pages: list[Page] = []

    def add(title: str, body: str) -> None:
        pages.append(Page(page_id=str(1_040_000 + len(pages) * 37), title=title, body=body))

    # --- the matrix pages: reference data authored as page layout ---
    sections = []
    for name, code in WAREHOUSES:
        sections.append(
            f"<h2>{name} ({code})</h2>"
            f"<p>Checks performed on receipt at {name}. Deviations are escalated to the "
            f"duty supervisor.</p>"
            f"{legend_block()}"
            f"{matrix_table(code)}"
        )
    add(
        "Receiving Checks by Warehouse",
        "<p>The table below lists every receiving check by shipment class and warehouse. "
        "It is the reference used by the receiving desks.</p>"
        + "".join(sections)
        + f"<p>Escalation routes are described in {link_to('Escalation Routes')}.</p>",
    )

    # --- a narrow matrix: the same structure at a size people overlook ---
    rows = "".join(
        f"<tr><td>{check}</td><td>{emoticon('tick')}</td>"
        f"<td>{emoticon('tick' if i % 2 else 'cross')}</td></tr>"
        for i, check in enumerate(CHECKS)
    )
    add(
        "Checks on Returned Goods",
        "<p>Returns follow a shorter list than inbound shipments.</p>"
        f"{legend_block()}"
        "<table><tbody><tr><th>Check</th><th>Customer return</th>"
        f"<th>Supplier return</th></tr>{rows}</tbody></table>",
    )

    # --- the glossary: a corpus defining its own vocabulary in passing ---
    add(
        "Glossary",
        "<h2>Terms used across the handbook</h2>"
        "<p>A Goods Received Note (GRN) is raised for every inbound pallet. The "
        "Temperature Excursion Report (TER) follows any breach recorded by the "
        "Temperature Log.</p>"
        "<p>Where a shipment arrives without paperwork the desk raises a Hold On Receipt "
        "(HOR) and notifies the Duty Supervisor (DS).</p>"
        "<p>ETA = Estimated Time of Arrival</p>"
        "<p>The Pallet Exchange Scheme (PES) applies at Harbour East and Harbour West "
        "only. Note that PES also refers to the Packaging Environmental Surcharge in "
        "supplier contracts, which is unrelated.</p>",
    )

    # --- process pages: one diagram readable, one not ---
    add(
        "Receiving Process",
        "<h2>From arrival to release</h2>"
        "<p>The diagram below shows the sequence followed at every warehouse.</p>"
        f"{process_svg()}"
        f"<p>Each step is described in {link_to('Receiving Checks by Warehouse')}.</p>",
    )
    add(
        "Cold Chain Handover",
        "<h2>Handover between carriers</h2>"
        "<p>The handover sequence is set out in the diagram.</p>"
        '<ac:image><ri:attachment ri:filename="cold-chain-handover.png" /></ac:image>'
        "<p>No written description of the sequence exists outside the diagram.</p>",
    )
    add(
        "Dock Layout",
        "<h2>Bay allocation</h2>"
        '<ac:image ac:alt="Bay allocation: inbound bays 1 to 4, outbound bays 5 to 8, '
        'refrigerated bay 9">'
        '<ri:attachment ri:filename="dock-layout.png" /></ac:image>'
        "<p>Bays are reallocated at the start of each shift.</p>",
    )
    add(
        "Escalation Routes",
        "<h2>Who to contact</h2>"
        '<ac:structured-macro ac:name="drawio" ac:schema-version="1">'
        '<ac:parameter ac:name="diagramName">Escalation</ac:parameter>'
        '<ac:parameter ac:name="border">false</ac:parameter></ac:structured-macro>'
        "<p>The duty supervisor is the first point of contact outside office hours.</p>",
    )

    # --- runbooks: ordinary prose with small tables ---
    runbooks = [
        ("Seal Integrity Check", "seal", "Compare the seal number against the manifest."),
        ("Weight Variance Check", "weight", "Weigh the pallet and compare to the declared mass."),
        ("Temperature Log Review", "temperature", "Download the logger and inspect the trace."),
        ("Hazard Labelling Check", "hazard", "Confirm the label class against the paperwork."),
        ("Customs Paperwork Check", "customs", "Confirm the entry number and the commodity code."),
        ("Pallet Condition Check", "pallet", "Inspect blocks and boards before acceptance."),
        ("Photo Evidence Capture", "photo", "Photograph all four faces before unwrapping."),
        ("Recipient Signature Capture", "signature", "Capture the signature on the handheld."),
    ]
    steps = [
        "Confirm the shipment reference against the manifest.",
        "Perform the check and note the reading.",
        "Record the outcome against the shipment.",
        "Photograph anything outside tolerance.",
        "Escalate any deviation to the duty supervisor.",
        "Close the task on the handheld before leaving the bay.",
    ]
    for title, slug, opening in runbooks:
        rows = "".join(
            f"<tr><td>{n}</td><td>{step}</td><td>Receiving desk</td>"
            f"<td>{emoticon('tick' if n < 5 else 'warning')}</td></tr>"
            for n, step in enumerate(steps, start=1)
        )
        add(
            title,
            f"<h2>Purpose</h2><p>{opening}</p>"
            "<h2>Steps</h2>"
            "<table><tbody>"
            "<tr><th>Step</th><th>Action</th><th>Owner</th><th>Recorded</th></tr>"
            f"{rows}</tbody></table>"
            f"<p>See also {link_to('Glossary')} and the {slug} entry in the archive.</p>",
        )

    # --- pages that exercise the awkward cases ---
    add(
        "Shift Handover Notes",
        "<h2>Recent notes</h2>"
        '<ac:structured-macro ac:name="pagetree" ac:schema-version="1">'
        '<ac:parameter ac:name="root">@self</ac:parameter></ac:structured-macro>'
        "<p>Notes are listed automatically.</p>",
    )
    add(
        "Warehouse Index",
        "<h2>All warehouse pages</h2>"
        '<ac:structured-macro ac:name="children" ac:schema-version="1" />',
    )
    add(
        "Capacity by Month",
        "<h2>Pallet positions</h2>"
        "<p>Figures are reviewed quarterly.</p>"
        "<table><tbody><tr><th>Month</th><th>Positions</th><th>Utilisation</th></tr>"
        "<tr><td>January</td><td>4200</td><td>71%</td></tr>"
        "<tr><td>February</td><td>4200</td><td>68%</td></tr>"
        "<tr><td>March</td><td>4400</td><td>77%</td></tr>"
        "<tr><td>Total</td><td>12800</td></tr>"
        "</tbody></table>"
        "<p>The final row is short by one column; it has been that way since the page was "
        "written.</p>",
    )
    add(
        "Equipment Register",
        "<h2>Handling equipment</h2>"
        "<table><tbody><tr><td>Asset</td><td>Site</td><td>Serviced</td></tr>"
        "<tr><td>Reach truck R-11</td><td>Harbour East</td><td>April</td></tr>"
        "<tr><td>Reach truck R-12</td><td>Harbour West</td><td>April</td></tr>"
        "<tr><td>Counterbalance C-04</td><td>Inland Depot</td><td>May</td></tr>"
        "</tbody></table>"
        "<p>The header row was never marked up as one.</p>",
    )
    add(
        "Packaging Standards",
        "<h2>Accepted packaging</h2>"
        "<table><tbody><tr><th>Type</th><th>Detail</th></tr>"
        "<tr><td>Euro pallet</td><td>1200 × 800"
        "<table><tbody><tr><td>Max height</td><td>1800 mm</td></tr>"
        "<tr><td>Max mass</td><td>1000 kg</td></tr></tbody></table></td></tr>"
        "<tr><td>Half pallet</td><td>800 × 600</td></tr></tbody></table>",
    )
    add(
        "Night Shift Exceptions",
        "<h2>Reduced checks</h2>"
        "<p>Between 22:00 and 06:00 a reduced list applies.</p>"
        "<table><tbody><tr><th>Check</th><th>Night shift</th></tr>"
        f"<tr><td>Seal Integrity</td><td>{emoticon('tick')}</td></tr>"
        f"<tr><td>Photo Evidence</td><td>{emoticon('nightshift-only')}</td></tr>"
        f"<tr><td>Weight Variance</td><td>{emoticon('cross')}</td></tr>"
        "</tbody></table>"
        "<p>One of the icons above is not part of the standard set.</p>",
    )
    add(
        "Carrier Contacts",
        "<h2>Contacts</h2>"
        f"<p>Routing questions go to the carrier desk. See {link_to('Carrier Onboarding')} "
        "for new carriers.</p>"
        '<p>External guidance: <a href="https://standards.example/packaging">packaging '
        "standards</a>.</p>",
    )
    add(
        "Hazardous Goods Handling",
        "<h2>Acceptance</h2>"
        "<p>Hazardous shipments are accepted at Harbour East and Cold Store only.</p>"
        f"<p>Labelling rules are described in {link_to('Hazard Labelling Check')}. "
        f"Storage segregation is covered in {link_to('Segregation Matrix')}.</p>",
    )
    rate_rows = "".join(
        f"<tr><td>{lane}</td><td>{days} days</td><td>{price}</td><td>{surcharge}</td></tr>"
        for lane, days, price, surcharge in [
            ("Harbour East to Inland Depot", 1, "42.00", "none"),
            ("Harbour West to Inland Depot", 1, "44.50", "none"),
            ("Harbour East to Cold Store", 2, "61.00", "temperature"),
            ("Inland Depot to Cold Store", 2, "58.00", "temperature"),
            ("Harbour West to Harbour East", 1, "27.50", "none"),
            ("Cold Store to Harbour East", 2, "63.00", "temperature"),
        ]
    )
    add(
        "Carrier Rate Card",
        "<h2>Indicative lane rates</h2>"
        "<p>Rates are indicative and reviewed each quarter.</p>"
        "<table><tbody><tr><th>Lane</th><th>Transit</th><th>Rate per pallet</th>"
        f"<th>Surcharge</th></tr>{rate_rows}</tbody></table>",
    )

    shift_rows = "".join(
        f"<tr><td>{site}</td><td>{early}</td><td>{late}</td><td>{night}</td></tr>"
        for site, early, late, night in [
            ("Harbour East", "06:00-14:00", "14:00-22:00", "22:00-06:00"),
            ("Harbour West", "06:00-14:00", "14:00-22:00", "closed"),
            ("Inland Depot", "07:00-15:00", "15:00-23:00", "closed"),
            ("Cold Store", "06:00-14:00", "14:00-22:00", "22:00-06:00"),
        ]
    )
    add(
        "Shift Schedule",
        "<h2>Standard shift pattern</h2>"
        "<p>Bank holidays follow the weekend pattern.</p>"
        "<table><tbody><tr><th>Site</th><th>Early</th><th>Late</th>"
        f"<th>Night</th></tr>{shift_rows}</tbody></table>",
    )

    contact_rows = "".join(
        f"<tr><td>{role}</td><td>{site}</td><td>{hours}</td><td>{route}</td></tr>"
        for role, site, hours, route in [
            ("Duty supervisor", "Harbour East", "24 hours", "Radio channel 2"),
            ("Duty supervisor", "Harbour West", "06:00-22:00", "Radio channel 3"),
            ("Customs liaison", "All sites", "08:00-18:00", "Customs desk"),
            ("Cold chain officer", "Cold Store", "24 hours", "Radio channel 5"),
            ("Site manager", "Inland Depot", "07:00-19:00", "Reception"),
        ]
    )
    add(
        "Site Contacts",
        "<h2>Who covers what</h2>"
        "<table><tbody><tr><th>Role</th><th>Site</th><th>Cover</th>"
        f"<th>Reach by</th></tr>{contact_rows}</tbody></table>"
        f"<p>Escalation beyond the duty supervisor follows {link_to('Escalation Routes')}.</p>",
    )

    add(
        "Handbook Home",
        "<h2>Warehouse operations handbook</h2>"
        f"<p>Start with {link_to('Receiving Process')}, then the "
        f"{link_to('Receiving Checks by Warehouse')} reference.</p>"
        f"<p>Definitions are collected in {link_to('Glossary')}.</p>",
    )
    return pages


def write_corpus() -> tuple[int, Path]:
    """Write the pages and the index that names them.

    A real export ships an index because the pages link to each other by *title* while the
    files are named by page id. Without it nothing resolves, so the demo corpus ships one
    too — and two of its links point at pages that do not exist, which is what a dangling
    reference looks like from the inside.
    """
    PAGES.mkdir(parents=True, exist_ok=True)
    for stale in PAGES.glob("*.html"):
        stale.unlink()

    pages = build_pages()
    for page in pages:
        PAGES.joinpath(f"{page.page_id}.html").write_text(page.body + "\n", encoding="utf-8")

    index = CORPUS / "index.csv"
    with index.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["filename", "title", "url"])
        for page in pages:
            writer.writerow(
                [
                    f"{page.page_id}.html",
                    page.title,
                    f"https://wiki.harbourline.example/display/OPS/{page.title.replace(' ', '+')}",
                ]
            )
    return len(pages), index


if __name__ == "__main__":
    count, index = write_corpus()
    print(f"wrote {count} pages to {PAGES} and an index to {index}")
