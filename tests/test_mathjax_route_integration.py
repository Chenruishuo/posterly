"""Chromium-gated integration test for the bundled-MathJax route in
``render.open_print_emulated_page``.

The route is what makes gate measurement deterministic offline: the
templates load MathJax v3 from the jsdelivr CDN, and the renderer
intercepts exactly that shape of URL and serves the skill's bundled
``assets/mathjax/tex-svg.js``. Pins three contracts:

  * a page using the templates' CDN URL typesets with the NETWORK
    DISABLED (the route, not the CDN, served the file);
  * the match is narrow -- a poster pointing at its OWN local vendored
    ``tex-svg.js`` loads that copy untouched (no silent version swap);
  * the bundle actually exists in the repo.

Skipped when Playwright/Chromium isn't installed.
"""
from __future__ import annotations

import pytest

from _posterly import render as _render


# Runtime fixture, not a collection-time skipif: the bundle-existence
# and URL-pattern tests need no browser and must run (not merely
# not-skip) on a Chromium-less CI without even ATTEMPTING a launch at
# collection time -- a missing bundle is exactly what such an
# environment should catch.
@pytest.fixture
def chromium():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
    except Exception:
        pytest.skip("Playwright/Chromium not available")

_PAGE = """<!doctype html><html><head>
<script>window.MathJax={tex:{inlineMath:[['$','$']]}};</script>
<script id="MathJax-script" async src="%s"></script>
</head><body><p>$E=mc^2$</p></body></html>"""

_CDN = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"


def test_bundle_exists() -> None:
    p = _render.bundled_mathjax_path()
    assert p is not None and p.stat().st_size > 1_000_000


def test_route_pattern_narrowness() -> None:
    """The interception regex must cover exactly the npm-mirror 3.x
    shape -- no version drift, no file:// vendored copies."""
    rx = _render._MATHJAX_CDN_RE
    assert rx.match(_CDN)
    assert rx.match("https://unpkg.com/npm/mathjax@3.2.2/es5/tex-svg.js")
    assert rx.match("http://cdn.jsdelivr.net/npm/mathjax@3.2/es5/tex-svg.js")
    assert not rx.match(
        "https://cdn.jsdelivr.net/npm/mathjax@4/es5/tex-svg.js")
    assert not rx.match(
        "https://cdn.jsdelivr.net/npm/mathjax@30/es5/tex-svg.js")
    assert not rx.match(
        "https://cdn.jsdelivr.net/npm/mathjax@3custom/es5/tex-svg.js")
    assert not rx.match(   # npm-layout-shaped LOCAL vendored copy
        "file:///poster/npm/mathjax@3.2.2/es5/tex-svg.js")
    assert not rx.match("file:///poster/mathjax/tex-svg.js")


def _typeset_count(tmp_path, src: str) -> int:
    from playwright.sync_api import sync_playwright

    f = tmp_path / "p.html"
    f.write_text(_PAGE % src, encoding="utf-8")
    with sync_playwright() as p:
        browser, ctx, page = _render.open_print_emulated_page(p, (800, 600))
        ctx.set_offline(True)  # only the route (or a local file) can serve
        page.goto(f.resolve().as_uri(), wait_until="networkidle",
                  timeout=15000)
        _render.settle_page(page, mathjax_timeout_ms=15000, settle_ms=100)
        n = page.evaluate(
            "() => document.querySelectorAll('mjx-container').length")
        browser.close()
    return n


def test_cdn_url_typesets_offline(chromium, tmp_path) -> None:
    assert _typeset_count(tmp_path, _CDN) == 1


def test_versioned_cdn_pin_also_matches(chromium, tmp_path) -> None:
    pin = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"
    assert _typeset_count(tmp_path, pin) == 1


def test_local_vendored_copy_not_intercepted(chromium, tmp_path) -> None:
    """A poster that vendored its own tex-svg.js must load THAT file --
    the narrow match must not swallow non-npm-shaped URLs. The sentinel
    'bundle' just sets a marker instead of typesetting."""
    from playwright.sync_api import sync_playwright

    (tmp_path / "mathjax").mkdir()
    (tmp_path / "mathjax" / "tex-svg.js").write_text(
        "window.__own_mathjax = true;", encoding="utf-8")
    f = tmp_path / "p.html"
    f.write_text(_PAGE % "mathjax/tex-svg.js", encoding="utf-8")
    with sync_playwright() as p:
        browser, _ctx, page = _render.open_print_emulated_page(p, (800, 600))
        page.goto(f.resolve().as_uri(), wait_until="networkidle",
                  timeout=15000)
        own = page.evaluate("() => window.__own_mathjax === true")
        n = page.evaluate(
            "() => document.querySelectorAll('mjx-container').length")
        browser.close()
    assert own is True   # the local file itself was served
    assert n == 0        # and nothing swapped in the real bundle
