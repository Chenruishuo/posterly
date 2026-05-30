"""Chromium-gated integration test for the CARD/TRAILING geometry inside
``polish``'s ``_POLISH_JS``.

The unit tests in ``test_polish_output.py`` feed the Python loop canned
``cards`` data and never execute the JS, so the DOM-geometry sampling
itself -- text-node ``Range`` measurement, absolutely-positioned-subtree
skip, and ``border-bottom`` subtraction -- is only exercised here, against
a real headless Chromium. These three were the substance of a review of
the original leaf-element scan, which:

  * undershot ``maxB`` when a plain-text tail wrapped below an inline
    ``<span>``/``<b>`` (the parent had element children, so it was skipped,
    and the inline leaf sat on an earlier line) -> FALSE POSITIVE;
  * was pulled to the card bottom by an absolutely-positioned corner
    badge, masking a real top-packed void above it -> FALSE NEGATIVE.

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


# Three adversarial cards in DOM order (card 0, 1, 2). Width is pinned so
# the prose in card 0 actually wraps; the `* { margin: 0 }` reset matches
# the shipped templates so card 0 has no default <p> margin inflating its
# trailing. Heights on cards 1 and 2 force the stretch the gate must catch.
_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .card { width: 300px; border: 2px solid #888; padding: 10px;
          margin: 12px; font-size: 14px; line-height: 1.3; background: #fff; }
  .kw { color: #2D5F8B; font-weight: 700; }
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <!-- card 0: natural height, inline <span> + wrapping plain-text tail.
         Correctly filled -> must NOT flag (the leaf-scan false positive). -->
    <div class="card" data-measure-role="card">
      <p>Start <span class="kw">KEYWORD</span> then a long continuation of
         plain text that wraps onto several lines and fills the card body
         all the way down so there is essentially no blank space below the
         last line of text in this card at all, none whatsoever, really.</p>
    </div>
    <!-- card 1: stretched, short top-packed content -> must flag (the real
         white-band the gate exists to catch). -->
    <div class="card" data-measure-role="card" style="height: 360px;">
      <p>Short line only.</p>
    </div>
    <!-- card 2: stretched, short content + ABS badge pinned at the bottom.
         The badge must NOT count as content bottom -> must still flag. -->
    <div class="card" data-measure-role="card"
         style="height: 360px; position: relative;">
      <p>Short line only.</p>
      <span class="kw" style="position:absolute; bottom:6px; right:8px;">QR</span>
    </div>
    <!-- card 3: content bottom is a PURE-CSS bar (no text, no img/svg).
         Correctly filled -> must NOT flag. The text+replaced scan alone
         would miss the empty <div> and false-positive; the leaf-box scan
         re-covers it. -->
    <div class="card" data-measure-role="card" style="height: 200px;">
      <p>Tiny label.</p>
      <div style="height: 150px; background: linear-gradient(#ddd,#bbb);
                  border-radius: 6px;"></div>
    </div>
  </div>
  </div>
</body></html>
"""


def _args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200,
        mathjax_timeout_ms=5000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10, strict=False,
    )


def test_card_trailing_geometry_end_to_end(tmp_path, capsys) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_HTML, encoding="utf-8")

    rc = _polish.cmd_polish(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 0                                  # warn-only, not --strict
    assert "cards checked       : 4" in combined    # all four sampled
    # card 0 is correctly filled -- the Range scan reaches its wrapped tail,
    # so it must NOT be flagged (the leaf-scan would have, falsely).
    assert "CARD/TRAILING: card 0" not in combined
    # cards 1 and 2 are genuine top-packed voids -- both must flag. Card 2
    # only flags because the absolutely-positioned badge is skipped.
    assert "CARD/TRAILING: card 1" in combined
    assert "CARD/TRAILING: card 2" in combined
    # card 3's bottom is a pure-CSS bar (no text/img) -- the leaf-box scan
    # counts it, so the card reads as filled and must NOT flag.
    assert "CARD/TRAILING: card 3" not in combined
