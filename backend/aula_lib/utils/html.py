"""HTML content conversion utilities."""

import logging

_LOGGER = logging.getLogger(__name__)

try:
    import html2text as _html2text
    _HAS_HTML2TEXT = True
except ImportError:
    _html2text = None
    _HAS_HTML2TEXT = False
    _LOGGER.warning("html2text not installed — HTML conversion will return raw HTML")


def html_to_plain(html: str) -> str:
    """Convert HTML to plain text, stripping links, images, and tables."""
    if not html:
        return ""
    if not _HAS_HTML2TEXT:
        return html
    try:
        h = _html2text.HTML2Text()
        h.unicode_snob = True
        h.images_to_alt = True
        h.single_line_break = True
        h.ignore_emphasis = True
        h.ignore_links = True
        h.ignore_images = True
        h.ignore_tables = True
        return h.handle(html).strip()
    except (ValueError, AttributeError, UnicodeError) as e:
        _LOGGER.warning("Error converting HTML to plain text: %s", e)
        return html


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown format."""
    if not html:
        return ""
    if not _HAS_HTML2TEXT:
        return html
    try:
        h = _html2text.HTML2Text()
        h.unicode_snob = True
        return h.handle(html).strip()
    except (ValueError, AttributeError, UnicodeError) as e:
        _LOGGER.warning("Error converting HTML to Markdown: %s", e)
        return html
