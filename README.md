# confluence-structure

Read Confluence storage-format exports without losing their structure.

Confluence stores pages in an XHTML dialect that keeps its own namespaces. An export in
that format carries more than the rendered page does — a status icon is a tag with a name
attribute, merged cells are declared rather than painted, and a macro records what it would
have generated. Extract the text and all of it is gone, silently.

This library reads the attributes instead.

> Early work in progress. Icons and table geometry are in place; the parser, a demo corpus
> and a measured comparison against text-only extraction are coming.

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

## Licence

MIT.
