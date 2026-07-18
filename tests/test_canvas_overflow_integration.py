"""Chromium-gated integration test for the canvas-overflow gate in
``measure`` (the ``scrollWidth/Height`` vs ``clientWidth/Height`` check on
the poster root in ``cmd_measure``).

The poster BOX can be exactly 24x36 in and page-aligned while its CONTENT
is wider (or taller) than the canvas and gets sliced off at the page
boundary -- an entire right/bottom strip vanishing in print. The
canvas-fill and position gates read the poster box; the clip gate scans
only card/column/hero/band; the spread/gap gates read vertical bottoms --
so nothing else catches it. The classic trigger is a ``.poster`` grid
with ``grid-template-rows`` but no ``grid-template-columns``: the implicit
``auto`` column grows to a wide child's max-content and every full-width
row overflows.

``scrollWidth/Height`` includes the overflowing content in BOTH overflow
modes (``hidden`` clips at the poster, ``visible`` spills past the page),
verified in Chromium, so the gate must fire for both. A well-formed
poster keeps ``scroll == client`` (MathJax's 1px-clipped a11y nodes don't
inflate it), so it must NOT false-fire.

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


# Full-bleed 24x36in poster (viewport 2304x3456 px). The `.poster` is a
# grid with only `grid-template-rows` -- no `grid-template-columns` -- so
# its single implicit `auto` column grows to the widest child. `wide`
# toggles a `white-space:nowrap` band far wider than the canvas (the
# overflow case) vs a wrapping band that fits (the clean case). `tall`
# toggles a fixed-height inner block taller than the canvas. `shrinkable`
# makes the band a REFLOW-able block (`width:3000px; max-width:100%`):
# under the implicit `auto` column it forces the column to 3000px and
# overflows, but with `col_fix` (which injects
# `grid-template-columns: minmax(0,1fr)`) the 1fr track caps the grid
# area and `max-width:100%` shrinks it to fit -- proving the column
# defense rescues reflow-able content (nowrap/fixed-px it cannot).
def _poster(*, overflow_css: str, wide: bool, tall: bool = False,
            col_fix: bool = False, shrinkable: bool = False) -> str:
    band_txt = (
        ("W" * 400) if wide
        else "a normal band that wraps and fits inside the canvas width"
    )
    tall_css = "height: 4000px;" if tall else ""
    shrink_css = "width: 3000px; max-width: 100%;" if shrinkable else ""
    col_css = "grid-template-columns: minmax(0, 1fr);" if col_fix else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: grid;
             {col_css}
             grid-template-rows: auto minmax(0, 1fr) auto;
             padding: 40px; overflow: {overflow_css}; }}
  .band {{ white-space: {"nowrap" if wide else "normal"};
           font-size: 40px; {tall_css} {shrink_css} }}
  .col {{ display: flex; flex-direction: column; min-height: 0; }}
  .card {{ flex: 1; border: 2px solid #888; }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="band">{band_txt}</div>
    <div class="col" data-measure-role="column">
      <div class="card" data-measure-role="card">card</div>
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


def _run(tmp_path, capsys, **poster_kw):
    poster = tmp_path / "poster.html"
    poster.write_text(_poster(**poster_kw), encoding="utf-8")
    rc = _measure.cmd_measure(_args(poster))
    return rc, "".join(capsys.readouterr())


def test_wide_content_overflow_hidden_fires(tmp_path, capsys) -> None:
    # Single-column grid, wide nowrap band, overflow:hidden -> content is
    # ~1.5x canvas width and clipped at the poster. The gate must fire and
    # name the right-edge overflow + the grid-template-columns fix.
    rc, out = _run(tmp_path, capsys, overflow_css="hidden", wide=True)
    assert rc == 1
    assert "scrollable overflow" in out
    assert "past the right edge" in out
    assert "grid-template-columns" in out


def test_wide_content_overflow_visible_fires(tmp_path, capsys) -> None:
    # Same overflow but overflow:visible -> content spills past the PAGE
    # boundary instead of the poster; scrollWidth still includes it, so
    # the gate must fire here too (this is the case no other gate sees).
    rc, out = _run(tmp_path, capsys, overflow_css="visible", wide=True)
    assert rc == 1
    assert "scrollable overflow" in out
    assert "past the right edge" in out


def test_fitting_content_no_false_positive(tmp_path, capsys) -> None:
    # A wrapping band that fits: scrollWidth == clientWidth -> the gate
    # stays silent and measure PASSes.
    rc, out = _run(tmp_path, capsys, overflow_css="hidden", wide=False)
    assert rc == 0
    assert "PASS" in out
    assert "scrollable overflow" not in out


def test_tall_content_overflow_fires(tmp_path, capsys) -> None:
    # A fixed-height inner block taller than the canvas overflows the
    # bottom edge -- scrollHeight > clientHeight -> the gate names the
    # bottom overflow.
    rc, out = _run(tmp_path, capsys, overflow_css="hidden", wide=False,
                   tall=True)
    assert rc == 1
    assert "scrollable overflow" in out
    assert "past the bottom edge" in out


def test_shrinkable_content_overflows_without_column_defense(
        tmp_path, capsys) -> None:
    # A REFLOW-able block (width:3000px capped by max-width:100%) under the
    # implicit `auto` column: the column grows to 3000px and the block
    # overflows the canvas -> gate fires. This is the exact class the
    # column defense is meant to rescue (unlike nowrap, which it can't).
    rc, out = _run(tmp_path, capsys, overflow_css="hidden", wide=False,
                   shrinkable=True, col_fix=False)
    assert rc == 1
    assert "scrollable overflow" in out
    assert "past the right edge" in out


def test_column_defense_rescues_reflowable_content(
        tmp_path, capsys) -> None:
    # SAME reflow-able block, now with grid-template-columns:minmax(0,1fr):
    # the 1fr track caps the grid area and max-width:100% shrinks the block
    # to fit -> no overflow, measure PASSes. This is what the shipped
    # templates' `.poster` column declaration actually buys.
    rc, out = _run(tmp_path, capsys, overflow_css="hidden", wide=False,
                   shrinkable=True, col_fix=True)
    assert rc == 0
    assert "PASS" in out
    assert "scrollable overflow" not in out
