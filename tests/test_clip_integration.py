"""Chromium-gated integration test for the content-clipping gate in
``measure`` (``_MEASURE_JS`` + the scroll-vs-client check in ``cmd_measure``).

``measure`` reads each element's border-box bottom to judge alignment. A
flex card/column with ``overflow: hidden`` (or ``clip``/``scroll``/``auto``)
decouples that box from the real content extent: the spec flips its
``min-height: auto`` to ``0``, so flexbox shrinks the over-full item back
inside the column and clips the overflow. The box then looks perfectly
aligned, ``measure`` reports a clean gap, and ``polish``'s CARD/TRAILING
check sees no blank space -- yet the content past the edge is silently lost
in print. This is the bug the gate exists to catch.

The check is render-time (computed ``overflow`` + ``scrollHeight`` vs
``clientHeight``), so it can only be exercised against a real headless
Chromium, not the mocked unit suite.

Verifies the gate FIRES on the clipped case, does NOT fire when the same
``overflow: hidden`` card's content actually fits (no false positive), and
does NOT fire on a visible overflow -- that path is left to the existing
gap gate, which the test confirms still catches it.

Skipped when Playwright/Chromium isn't installed.
"""
from __future__ import annotations

import argparse

import pytest

from _posterly import measure as _measure


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _chromium_available(),
    reason="playwright + chromium not available",
)


# Full-bleed 24x36in poster (viewport 2304x3456 px at 96 ppi) so it clears
# measure's canvas-fill + position gates; a single flex column + flex card
# keeps spread = 0; the footer-strip's 40 px top margin puts the gap in the
# [30, 50] band. The card's `overflow` rule and content length are the only
# variables -- everything else is held constant so the clip gate is what the
# assertions isolate.
def _poster(overflow_css: str, paragraphs: int) -> str:
    para = ("<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore.</p>")
    content = para * paragraphs
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: flex; flex-direction: column; padding: 60px; }}
  .column {{ flex: 1; display: flex; flex-direction: column; min-height: 0; }}
  .card {{ flex: 1; border: 2px solid #888; padding: 20px;
           display: flex; flex-direction: column; {overflow_css} }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233; }}
  p {{ font-size: 28px; line-height: 1.4; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">
        {content}
      </div>
    </div>
    <div class="footer-strip" data-measure-role="footer-strip"></div>
  </div>
</body></html>
"""


def _args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None,
        max_spread=5.0, min_gap=30.0, max_gap=50.0,
        allow_empty_column=False, allow_no_footer_gap=False,
        settle_ms=200, mathjax_timeout_ms=5000,
        min_canvas_fill=0.95, max_canvas_fill=1.01,
        position_tol_px=2.0, max_clip_px=2.0, json_out=None,
    )


def _run(tmp_path, capsys, overflow_css: str, paragraphs: int):
    poster = tmp_path / "poster.html"
    poster.write_text(_poster(overflow_css, paragraphs), encoding="utf-8")
    rc = _measure.cmd_measure(_args(poster))
    return rc, "".join(capsys.readouterr())


def test_overflow_hidden_clip_fires(tmp_path, capsys) -> None:
    # overflow:hidden + far too much content -> flexbox shrinks the card and
    # clips ~thousands of px; the gate must hard-fail and name the clip.
    rc, out = _run(tmp_path, capsys, "overflow: hidden;", paragraphs=80)
    assert rc == 1
    assert "CLIPPED" in out
    assert "overflow-y: hidden" in out


def test_content_fits_no_false_positive(tmp_path, capsys) -> None:
    # Same overflow:hidden card, but the content easily fits -> scrollHeight
    # <= clientHeight, so the clip gate must stay silent and measure PASSes.
    rc, out = _run(tmp_path, capsys, "overflow: hidden;", paragraphs=1)
    assert rc == 0
    assert "PASS" in out
    assert "CLIPPED" not in out


def test_visible_overflow_is_gap_failure_not_clip(tmp_path, capsys) -> None:
    # Same over-full content but overflow:visible -> the card spills VISIBLY,
    # so the clip gate must NOT fire; the existing gap gate catches it via a
    # negative gap. This pins the boundary between the two gates.
    rc, out = _run(tmp_path, capsys, "", paragraphs=80)
    assert rc == 1
    assert "CLIPPED" not in out
    assert "min gap" in out


# A hero panel feeds spread/gap just like a card/column, and the shipped
# hero template's `.hero` is itself `overflow: hidden` -- so the same clip
# trap applies and the gate must cover the `hero` role too.
def _hero_poster(paragraphs: int) -> str:
    para = ("<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore.</p>")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: flex; flex-direction: column; padding: 60px; }}
  .hero {{ flex: 1; border: 2px solid #888; padding: 20px;
           display: flex; flex-direction: column; overflow: hidden; }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233; }}
  p {{ font-size: 28px; line-height: 1.4; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <section class="hero" data-measure-role="hero">
      {para * paragraphs}
    </section>
    <div class="footer-strip" data-measure-role="footer-strip"></div>
  </div>
</body></html>
"""


def test_hero_overflow_hidden_clip_fires(tmp_path, capsys) -> None:
    # A flex:1 hero with overflow:hidden + far too much content clips just
    # like a card -- the gate must fire (hero is in scope).
    poster = tmp_path / "poster.html"
    poster.write_text(_hero_poster(80), encoding="utf-8")
    rc = _measure.cmd_measure(_args(poster))
    out = "".join(capsys.readouterr())
    assert rc == 1
    assert "CLIPPED" in out
    assert "hero" in out
