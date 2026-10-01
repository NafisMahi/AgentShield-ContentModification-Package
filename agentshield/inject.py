"""Build the hidden-prompt markup used by `export` and `inject`.

Two embedding methods:
  - css    : a zero-size, transparent, offscreen <span> (selectable as text)
  - canvas : low-opacity text painted onto a <canvas> via fillText

`inject` writes injected copies of local static HTML to an output folder; the
site's stored content is not modified.
"""
from __future__ import annotations

import html
import json

from bs4 import BeautifulSoup

CSS_CLASS = "zero-text-injection"

# Hidden-text style: zero size, transparent, clipped, but still selectable.
_CSS_RULE = (
    ".%s {"
    " position: absolute;"
    " top: 0; left: 0;"
    " color: transparent !important;"
    " font-size: 0px !important;"
    " line-height: 0 !important;"
    " clip: rect(0, 0, 0, 0);"
    " width: 1px; height: 1px;"
    " overflow: hidden;"
    " user-select: text;"
    " }" % CSS_CLASS
)


def _css_markup(text):
    return (f"<style>{_CSS_RULE}</style>"
            f'<span class="{CSS_CLASS}">{html.escape(text)}</span>')


def _canvas_markup(text):
    # json.dumps -> safe JS string literal; guard against premature </script> close.
    js = json.dumps(text).replace("</", "<\\/")
    return (
        '<canvas id="ashid" width="900" height="16"></canvas>'
        '<script>'
        'var _ac=document.getElementById("ashid").getContext("2d");'
        '_ac.font="15px sans-serif";'
        '_ac.fillStyle="rgba(180,180,180,0.15)";'
        f'_ac.fillText({js},10,12);'
        '</script>'
    )


def _injection_markup(text, methods):
    parts = []
    if "css" in methods:
        parts.append(_css_markup(text))
    if "canvas" in methods:
        parts.append(_canvas_markup(text))
    return "\n".join(parts)


def build_markup(text, methods):
    """Return the hidden-prompt HTML snippet for the given text and methods."""
    return _injection_markup(text, methods)


def inject_into_html(page_html, text, methods):
    """Return a copy of page_html with the hidden prompt embedded at the start of <body>."""
    soup = BeautifulSoup(page_html, "html.parser")
    target = soup.body or soup
    fragment = BeautifulSoup(_injection_markup(text, methods), "html.parser")
    # Insert fragment nodes at the very start of <body>, preserving their order.
    for node in reversed(list(fragment.children)):
        target.insert(0, node)
    return str(soup)
