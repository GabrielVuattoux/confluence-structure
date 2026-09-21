"""Read Confluence storage-format exports without losing their structure.

Confluence stores pages in an XHTML dialect that keeps its own namespaces — ``ac:`` for
macros and markup, ``ri:`` for resource identifiers. An export in that format carries more
than the rendered page does: a status icon is a tag with a name attribute, a table's merged
cells are declared rather than painted, and a macro records what it would have generated.

Reading such a page as text throws all of that away. This package reads the attributes.
"""

__version__ = "0.1.0"
