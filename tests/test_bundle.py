"""bundle tests: reference rewriting (``src=`` / CSS ``url()``), the
references that must be left alone (fragments, existing data: URIs,
``data-src``, anything inside a comment or a script body), the MathJax
CDN swap and its narrowness, and the hard-failure contract -- a bundle
that would still point outside itself must not be written at all."""
from __future__ import annotations

import argparse
import base64

from _posterly import bundle

# 1x1 transparent PNG.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAA"
    "AAYAAjCB0C8AAAAASUVORK5CYII="
)
_CDN = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"


def _args(html, out=None, allow_remote=False):
    return argparse.Namespace(html=str(html), out=(str(out) if out else None),
                              allow_remote=allow_remote)


def _poster(tmp_path, body: str, *, with_png: bool = True):
    """Write a minimal poster; return its path."""
    if with_png:
        (tmp_path / "images").mkdir(exist_ok=True)
        (tmp_path / "images" / "fig.png").write_bytes(_PNG)
    html = tmp_path / "poster.html"
    html.write_text(f"<!DOCTYPE html>\n<html><head></head><body>{body}"
                    "</body></html>", encoding="utf-8")
    return html


def _run(tmp_path, body, *, out="out.html", allow_remote=False, **kw):
    html = _poster(tmp_path, body, **kw)
    out_path = tmp_path / out
    rc = bundle.cmd_bundle(_args(html, out_path, allow_remote))
    text = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
    return rc, out_path, text


# --- what gets inlined -------------------------------------------------

def test_img_src_becomes_data_uri(tmp_path) -> None:
    rc, _, text = _run(tmp_path, '<img src="images/fig.png" alt="f">')
    assert rc == 0
    assert "data:image/png;base64," in text
    assert 'src="images/fig.png"' not in text


def test_css_url_quoted_and_bare_both_inlined(tmp_path) -> None:
    body = ('<style>.a{background:url("images/fig.png")}'
            '.b{background:url(images/fig.png)}'
            ".c{background:url('images/fig.png')}</style>")
    rc, _, text = _run(tmp_path, body)
    assert rc == 0
    assert text.count("data:image/png;base64,") == 3
    assert "images/fig.png" not in text


def test_font_face_src_is_inlined(tmp_path) -> None:
    """A vendored-font poster is the case that breaks worst on delivery:
    the woff2 files travel with the directory, not the file."""
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "x.woff2").write_bytes(b"wOF2fake")
    body = ("<style>@font-face{font-family:X;"
            "src:url('fonts/x.woff2') format('woff2')}</style>")
    rc, _, text = _run(tmp_path, body)
    assert rc == 0
    assert "data:font/woff2;base64," in text
    assert "fonts/x.woff2" not in text


def test_percent_encoded_and_query_refs_resolve(tmp_path) -> None:
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "my fig.png").write_bytes(_PNG)
    rc, _, text = _run(tmp_path, '<img src="images/my%20fig.png?v=2">')
    assert rc == 0
    assert "data:image/png;base64," in text


def test_quoted_css_url_may_contain_parentheses(tmp_path) -> None:
    """``url("plot (final).png")`` is legal CSS and a filename users
    really produce. A pattern that stops at the first ``)`` misses it
    AND never records it -- the bundle would PASS still depending on a
    file it never inlined."""
    image = tmp_path / "plot (final).png"
    image.write_bytes(b"png")
    report = bundle.BundleReport()
    result = bundle.inline_references(
        'background-image: url("plot (final).png")', tmp_path, report
    )
    assert result == 'background-image: url("data:image/png;base64,cG5n")'
    assert report.missing == []


# --- what must be left alone -------------------------------------------

def test_svg_fragment_url_untouched(tmp_path) -> None:
    """``url(#psReg)`` is the identity glyph's paint reference, not a
    file -- rewriting it would erase the registration mark."""
    rc, _, text = _run(tmp_path, '<style>.m{fill:url(#psReg)}</style>')
    assert rc == 0
    assert "url(#psReg)" in text


def test_existing_data_uri_untouched(tmp_path) -> None:
    body = '<img src="data:image/png;base64,AAAA">'
    rc, _, text = _run(tmp_path, body)
    assert rc == 0
    assert 'src="data:image/png;base64,AAAA"' in text


def test_data_src_attribute_not_rewritten(tmp_path) -> None:
    """``\\bsrc`` would match inside ``data-src`` -- ``-`` is a word
    boundary. Only a real attribute boundary counts."""
    rc, _, text = _run(tmp_path, '<img data-src="images/fig.png" '
                                 'src="images/fig.png">')
    assert rc == 0
    assert 'data-src="images/fig.png"' in text
    assert text.count("data:image/png;base64,") == 1


def test_anchor_href_not_inlined(tmp_path) -> None:
    rc, _, text = _run(tmp_path, '<a href="images/fig.png">paper</a>')
    assert rc == 0
    assert 'href="images/fig.png"' in text


def test_commented_and_script_body_references_are_inert(tmp_path) -> None:
    """All three shipped templates carry commented-out
    ``<img src="assets/paper_figures/...">`` scaffolding examples. Read
    as live references they hard-fail a perfectly good poster on
    "missing local file". ``src=`` / ``url(…)`` inside an inline script
    is JavaScript string data, not a reference either."""
    (tmp_path / "live.png").write_bytes(b"png")
    text = (
        '<!-- <img src="missing-comment.png"> -->\n'
        "<script>const sample = '<img src=\"missing-script.png\">'; "
        "const css = 'url(missing-script.png)';</script>\n"
        '<img src="live.png">\n'
        "<style>/* url(missing-comment.png) */</style>\n"
    )
    report = bundle.BundleReport()
    result = bundle.inline_references(text, tmp_path, report)
    assert '<!-- <img src="missing-comment.png"> -->' in result
    assert 'src="missing-script.png"' in result
    assert "url(missing-script.png)" in result
    assert "/* url(missing-comment.png) */" in result
    assert 'src="data:image/png;base64,cG5n"' in result
    assert report.missing == []


# --- MathJax ------------------------------------------------------------

def test_mathjax_cdn_script_inlined(tmp_path) -> None:
    body = f'<script id="MathJax-script" async src="{_CDN}"></script>'
    rc, _, text = _run(tmp_path, body)
    assert rc == 0
    assert _CDN not in text
    assert bundle._MATHJAX_SLOT not in text
    assert 'id="MathJax-script"' in text          # attributes preserved
    assert "MathJax" in text and len(text) > 500_000   # runtime is there


def test_mathjax_v4_url_not_downgraded(tmp_path) -> None:
    """The CDN match is deliberately narrow (shared with the render
    gates). A mathjax@4 URL is a genuine remote dependency the bundler
    cannot satisfy -- it must fail loudly, not silently ship 3.x."""
    v4 = "https://cdn.jsdelivr.net/npm/mathjax@4/es5/tex-svg.js"
    rc, out_path, _ = _run(tmp_path, f'<script src="{v4}"></script>')
    assert rc == 1
    assert not out_path.exists()


def test_commented_mathjax_script_is_not_inlined() -> None:
    text = (f'<!-- <script src="{_CDN}"></script> -->')
    report = bundle.BundleReport()
    result, runtime = bundle.extract_mathjax(text, report)
    assert result == text
    assert runtime == ""
    assert report.mathjax_bytes == 0


def test_local_vendored_mathjax_becomes_data_uri(tmp_path) -> None:
    (tmp_path / "mathjax").mkdir()
    (tmp_path / "mathjax" / "tex-svg.js").write_text("window.MathJax=1;")
    rc, _, text = _run(tmp_path,
                       '<script src="mathjax/tex-svg.js"></script>')
    assert rc == 0
    assert "data:text/javascript;base64," in text


# --- hard-failure contract ---------------------------------------------

def test_missing_local_file_fails_and_writes_nothing(tmp_path) -> None:
    rc, out_path, _ = _run(tmp_path, '<img src="images/gone.png">')
    assert rc == 1
    assert not out_path.exists()


def test_remote_image_fails_by_default(tmp_path) -> None:
    rc, out_path, _ = _run(tmp_path,
                           '<img src="https://example.org/fig.png">')
    assert rc == 1
    assert not out_path.exists()


def test_allow_remote_banner_and_status_are_honest(tmp_path, capsys) -> None:
    """The banner is a claim made to whoever opens the delivered file.
    With a remote dependency kept, claiming "no network" would be a
    lie shipped inside the artifact."""
    rc, out_path, text = _run(tmp_path,
                              '<img src="https://example.com/figure.png">',
                              allow_remote=True)
    assert rc == 0
    assert "BUNDLE WITH REMOTE REFERENCES" in text
    assert "still need" in text and "a network" in text
    assert "SELF-CONTAINED BUNDLE" not in text
    assert "PASS -- bundle written; NOT self-contained" in capsys.readouterr().out


def test_link_stylesheet_fails(tmp_path) -> None:
    """The poster contract keeps all CSS in a <style> block; a linked
    sheet would be silently dropped from the bundle."""
    rc, out_path, _ = _run(tmp_path, '<link rel="stylesheet" href="a.css">')
    assert rc == 1
    assert not out_path.exists()


def test_missing_input_and_in_place_output_are_usage_errors(tmp_path) -> None:
    """Usage errors exit 2 (the convention verify-final already uses);
    exit 1 stays reserved for "the poster could not be bundled"."""
    missing = _args(tmp_path / "missing.html")
    assert bundle.cmd_bundle(missing) == bundle.EXIT_USAGE

    html = _poster(tmp_path, '<img src="images/fig.png">')
    before = html.read_text(encoding="utf-8")
    assert bundle.cmd_bundle(_args(html, html)) == bundle.EXIT_USAGE
    assert html.read_text(encoding="utf-8") == before


def test_default_out_path_is_stem_standalone(tmp_path) -> None:
    html = _poster(tmp_path, '<img src="images/fig.png">')
    assert bundle.cmd_bundle(_args(html)) == 0
    assert (tmp_path / "poster_standalone.html").is_file()


# --- report -------------------------------------------------------------

def test_duplicate_reference_is_reported(tmp_path, capsys) -> None:
    rc, _, text = _run(tmp_path, '<img src="images/fig.png">'
                                 '<img src="images/fig.png">')
    assert rc == 0
    assert text.count("data:image/png;base64,") == 2
    assert "inlined 2x" in capsys.readouterr().out


def test_banner_follows_doctype(tmp_path) -> None:
    rc, _, text = _run(tmp_path, "<p>hi</p>")
    assert rc == 0
    assert text.lstrip().lower().startswith("<!doctype html>")
    assert "SELF-CONTAINED BUNDLE" in text
