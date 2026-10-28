"""A4 PDF preview for a minuta template. Same page box as the editor sheet."""

from __future__ import annotations

from weasyprint import HTML, default_url_fetcher

_PAGE_CSS = """
@page {
  size: A4;
  margin: 20mm;
}
html, body {
  margin: 0;
  padding: 0;
}
body {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 15px;
  line-height: 1.625;
  color: #0f172a;
}
p { margin: 0.5em 0; }
p:first-child { margin-top: 0; }
h1 { font-size: 1.5rem; font-weight: 700; margin: 1.25em 0 0.75em; line-height: 1.25; }
h2 { font-size: 1.25rem; font-weight: 600; margin: 1em 0 0.5em; line-height: 1.25; }
h3 { font-size: 1.125rem; font-weight: 600; margin: 0.75em 0 0.375em; line-height: 1.25; }
ul, ol { margin: 0.5em 0; padding-left: 1.5em; }
blockquote {
  margin: 0.5em 0;
  padding-left: 1em;
  border-left: 4px solid #94a3b8;
  color: #475569;
  font-style: italic;
}
hr { margin: 1.5em 0; border: none; border-top: 1px solid #cbd5e1; }
code { font-family: ui-monospace, monospace; font-size: 0.9em; background: #f1f5f9; padding: 0.1em 0.25em; border-radius: 3px; }
pre { font-family: ui-monospace, monospace; font-size: 0.75rem; background: #f8fafc; border: 1px solid #e2e8f0; padding: 0.75em; border-radius: 6px; }
table { border-collapse: collapse; width: 100%; font-size: 15px; }
td, th { border: 1px solid #cbd5e1; padding: 0.75em; vertical-align: top; text-align: left; }
table.borderless td, table.borderless th { border: none; }
th { background: #f1f5f9; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; }
img { max-width: 100%; height: auto; margin: 1em 0; }
a { color: #6d28d9; text-decoration: underline; }
mark { border-radius: 2px; padding: 0 2px; }
sub { font-size: 0.75em; vertical-align: sub; }
sup { font-size: 0.75em; vertical-align: super; }
"""


def wrap_minuta_html(body_fragment: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="utf-8">
<style>{_PAGE_CSS}</style>
</head>
<body>{body_fragment}</body>
</html>"""


def _fetch_local(url: str, timeout: int = 10, ssl_context=None):
    if url.startswith("data:"):
        return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
    return {"string": b"", "mime_type": "text/plain"}


def render_minuta_pdf(body_html: str) -> bytes:
    html = wrap_minuta_html(body_html or "<p></p>")
    return HTML(string=html, url_fetcher=_fetch_local).write_pdf()
