# confluence-structure

Read Confluence storage-format exports without losing their structure.

Confluence stores pages in an XHTML dialect that keeps its own namespaces. An export in
that format carries more than the rendered page does — a status icon is a tag with a name
attribute, merged cells are declared rather than painted, and a macro records what it would
have generated. Extract the text and all of it is gone, silently.

This library reads the attributes instead.

> Early work in progress. Reading a page works end to end; a demo corpus and a measured
> comparison against text-only extraction are coming.

## Reading a page

```python
from pathlib import Path
from confluence_structure.parser import parse_file

page = parse_file(Path("export/123456.html"))

page.sections        # prose, split at its headings
page.tables          # expanded grids, merged cells resolved
page.figures         # diagrams, with whatever text could be read out of them
page.references      # page links (by title) and external URLs
page.attachments     # files the page depends on
page.macros          # including the ones whose body only exists at render time

page.trustworthy     # False if any table's geometry did not resolve cleanly
```

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

## Licence

MIT.
