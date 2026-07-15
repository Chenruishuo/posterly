"""Chromium-gated integration tests for the keybox two-line label
reservation (``min-height: 2lh``) and its interplay with polish's
CARD/TRAILING probe.

Two invariants:

1. **Alignment**: with the reservation, a 1-line-label tile's big
   number lands at the same y as a 2-line neighbour's (the pre-fix
   defect: centred tiles with different content heights put the
   numbers at different y).
2. **No masking**: the reserved-but-empty second label line must NOT
   read as card content -- an unpainted text leaf contributes only its
   text rects to the CARD/TRAILING content bottom, so a real trailing
   void below a keybox still flags. A PAINTED leaf (callout pill) at
   the card bottom still counts to its box edge (no false positive).

Skipped when Playwright / Chromium isn't installed.
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


# Mirrors the template keybox CSS (grid + centred flex tiles + 2lh
# label reservation) without dragging in a whole template.
_KEYBOX_CSS = """
  .keybox { display: grid; grid-template-columns: repeat(3, 1fr);
            gap: 16px; }
  .kb-item { background: #eef1f5; border-top: 6px solid #345;
             padding: 12px; text-align: center;
             display: flex; flex-direction: column;
             justify-content: center; }
  .kb-num { font-weight: 800; font-size: 48px; line-height: 1; }
  .kb-label { font-size: 18px; line-height: 1.1; margin-top: 6px;
              min-height: 2lh; }
"""

_ALIGN_HTML = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; padding: 60px; }}
  {_KEYBOX_CSS}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="keybox">
      <div class="kb-item"><div class="kb-num" id="n1">3.2x</div>
        <div class="kb-label">faster</div></div>
      <div class="kb-item"><div class="kb-num" id="n2">92%</div>
        <div class="kb-label">accuracy on the long two line
          benchmark suite label</div></div>
      <div class="kb-item"><div class="kb-num" id="n3">7</div>
        <div class="kb-label">datasets</div></div>
    </div>
  </div>
</body></html>
"""


def test_reservation_aligns_numbers(tmp_path) -> None:
    from playwright.sync_api import sync_playwright

    poster = tmp_path / "poster.html"
    poster.write_text(_ALIGN_HTML, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 2304, "height": 3456})
        page.emulate_media(media="print")
        page.goto(poster.as_uri())
        tops = page.evaluate(
            "() => ['n1','n2','n3'].map(i =>"
            " document.getElementById(i).getBoundingClientRect().top)"
        )
        # Sanity: the reservation actually reserves two lines even for
        # a 1-line label (label boxes equal height across tiles).
        label_hs = page.evaluate(
            "() => Array.from(document.querySelectorAll('.kb-label'))"
            ".map(e => e.getBoundingClientRect().height)"
        )
        browser.close()
    assert max(tops) - min(tops) < 1.0, tops
    assert max(label_hs) - min(label_hs) < 1.0, label_hs


# A card whose keybox (with the 2lh reservation) is the LAST content,
# followed by a large genuine void: the unpainted 1-line labels'
# reserved boxes must not mask it. Card is 1500px tall; content ends
# ~<600px -> trailing far beyond the 10% threshold.
_TRAILING_HTML = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; padding: 60px; }}
  .card {{ border: 2px solid #888; padding: 20px; height: 1500px; }}
  .card + .card {{ margin-top: 24px; }}
  {_KEYBOX_CSS}
  /* margin-top sized so the callout's PAINTED box ends ~60px above
     the card's inner bottom (~4% trailing, under the 10% threshold):
     the box bump, not the text inside it, is what must count. */
  .callout {{ background: #dde6f2; border-left: 8px solid #345;
              padding: 16px; margin-top: 1300px; }}
  p {{ font-size: 28px; line-height: 1.4; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">
        <p>Intro line.</p>
        <div class="keybox">
          <div class="kb-item"><div class="kb-num">3.2x</div>
            <div class="kb-label">faster</div></div>
          <div class="kb-item"><div class="kb-num">92%</div>
            <div class="kb-label">acc</div></div>
          <div class="kb-item"><div class="kb-num">7</div>
            <div class="kb-label">sets</div></div>
        </div>
        <!-- ~900px of genuine void below the keybox -->
      </div>
      <div class="card" data-measure-role="card">
        <p>Second card.</p>
        <!-- Painted leaf pushed low by margin: its painted box IS the
             content bottom, so this card must NOT flag. -->
        <div class="callout">Painted takeaway pill.</div>
      </div>
    </div>
  </div>
</body></html>
"""


def _polish_args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200,
        mathjax_timeout_ms=5000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, tall_min_ratio=0.36, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10, strict=False,
    )


def test_reservation_does_not_mask_trailing_void(
    tmp_path, capsys
) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_TRAILING_HTML, encoding="utf-8")
    rc = _polish.cmd_polish(_polish_args(poster))
    combined = "".join(capsys.readouterr())
    assert rc == 0  # warn-only
    # Card 0: keybox reservation must not hide the 900px void.
    assert "CARD/TRAILING: card 0" in combined
    # Card 1: the painted callout's box counts as content -- no warn.
    assert "CARD/TRAILING: card 1" not in combined
