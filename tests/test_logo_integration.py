"""Chromium-gated integration test for the Gate E (header logo) geometry
inside ``polish``'s ``_POLISH_JS``.

The unit tests in ``test_polish_output.py`` feed the Python loop canned
``logos``/``qrs``/``headerBlocks`` data and never execute the JS, so the
DOM collection itself -- the ``.logo-slot``/``.venue-badge`` scan, the QR
height sampling, and the header-block rects the squeeze gate reads -- is
only exercised here, against a real headless Chromium.

Skipped when Playwright/Chromium isn't installed (e.g. the mocked unit
suite runs under a plain interpreter with no browser).
"""
from __future__ import annotations

import argparse

import pytest

from _posterly import polish as _polish


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

_SVG = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
        "viewBox='0 0 10 10'><rect width='10' height='10' "
        "fill='%232D5F8B'/></svg>")

# The shipped templates' header skeleton: auto | 1fr | auto grid, flex
# right-block of logo slots + QR. Width pinned to 1000px so the gate
# fractions are exact.
_HEAD = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; box-sizing: border-box; }}
  .header {{ width: 1000px; display: grid;
             grid-template-columns: auto 1fr auto; align-items: center; }}
  .title-block {{ min-width: 0; }}
  .right-block {{ display: flex; align-items: center; gap: 10px; }}
  .logo-slot img, .qr-block img {{ display: block; }}
</style></head>
<body>
  <div data-measure-role="poster">
  <header class="header" data-measure-role="header">
    {venue}
    <div class="title-block"><h1>Poster title</h1></div>
    <div class="right-block">
      {slots}
      <div class="qr-block"><img src="{svg}"
           style="width:85px;height:85px"></div>
    </div>
  </header>
  <div data-measure-role="column">
    <div data-measure-role="card"><p>body</p>{body}</div>
  </div>
  </div>
</body></html>
"""

_TEXT_VENUE = '<div class="venue-badge">VENUE</div>'


def _args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200,
        mathjax_timeout_ms=5000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, tall_min_ratio=0.36, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10,
        logo_max_width_ratio=0.22, logo_qr_tol=0.15,
        rightblock_max_ratio=0.32, title_min_ratio=0.45, strict=False,
    )


def test_logo_gates_end_to_end(tmp_path, capsys) -> None:
    """Three adversarial logos: an oversized wordmark (30% of the 1000px
    header -> LOGO/WIDE), a too-tall seal (140px vs 85px QR ->
    LOGO/QR-MISMATCH), and a 404'd raster (-> LOGO/BROKEN). The fat
    right-block also squeezes the title -> HEADER/TITLE-SQUEEZED."""
    slots = f"""
      <div class="logo-slot">
        <img src="{_SVG}" style="width:300px;height:80px"></div>
      <div class="logo-slot">
        <img src="{_SVG}" style="width:100px;height:140px"></div>
      <div class="logo-slot">
        <img src="missing-logo.png" style="width:80px;height:80px"></div>
    """
    poster = tmp_path / "poster.html"
    poster.write_text(
        _HEAD.format(venue=_TEXT_VENUE, slots=slots, body="", svg=_SVG),
        encoding="utf-8")

    rc = _polish.cmd_polish(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 0                                  # warn-only, not --strict
    assert "header logos        : 3" in combined    # all three collected
    assert "LOGO/WIDE" in combined                  # 300/1000 = 30% > 22%
    assert "LOGO/QR-MISMATCH" in combined           # 140 vs 85 = 65% off
    assert "LOGO/BROKEN" in combined                # 404'd raster
    assert "missing-logo.png" in combined
    # ~595px right-block on a 1000px header steals the title's width.
    assert "HEADER/TITLE-SQUEEZED" in combined


def test_healthy_header_is_silent(tmp_path, capsys) -> None:
    """A header following the template defaults -- one 2:1 logo at the QR's
    85px height, 17% of header width -- must pass every Gate E check (the
    false-positive guard for the recommended size classes). Three traps
    prove the scoping rules:

    * a venue logo nested as ``.venue-badge > .logo-slot > img`` at 40px
      (vs the 85px QR) is collected ONCE and as venue -> no QR match
      (double-counting would emit a bogus LOGO/QR-MISMATCH);
    * a card-body ``.logo-slot`` at 300px and a card-body ``.qr-block``
      at 40px are OUTSIDE the header -> not collected (they'd otherwise
      fire LOGO/WIDE and corrupt the QR height)."""
    venue = f"""<div class="venue-badge"><div class="logo-slot">
        <img src="{_SVG}" style="width:40px;height:40px"></div></div>"""
    slots = f"""
      <div class="logo-slot">
        <img src="{_SVG}" style="width:170px;height:85px"></div>
    """
    body = f"""
      <div class="logo-slot">
        <img src="{_SVG}" style="width:300px;height:85px"></div>
      <div class="qr-block">
        <img src="{_SVG}" style="width:40px;height:40px"></div>
    """
    poster = tmp_path / "poster.html"
    poster.write_text(
        _HEAD.format(venue=venue, slots=slots, body=body, svg=_SVG),
        encoding="utf-8")

    rc = _polish.cmd_polish(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 0
    assert "header logos        : 2" in combined   # body decoys not counted
    assert "LOGO/" not in combined
    assert "HEADER/TITLE-SQUEEZED" not in combined
