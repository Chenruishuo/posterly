"""Chromium-gated integration tests for the three gates added after a real
A0 band-stack poster shipped every gate green with visible defects:

  * ``CARD/TRACK-MISALIGN`` -- side-by-side ``.track`` columns inside one
    card whose content bottoms end far apart (the short column strands a
    void at its foot). CARD/TRAILING reads only the card bottom (hugged by
    the tallest track), the inner-void walk merges side-by-side children
    into one row, and TRACK/INNER-VOID runs only on header/footer roles --
    so this geometry was invisible to every prior gate.
  * ``FIG/PAIR-GEOMETRY`` -- images declaring shared crop geometry via
    ``data-crop-lock`` whose natural aspect ratios disagree (the real case:
    one matched panel cropped 7 px shorter, slicing its label row).
  * ``CARD/TRAILING``'s absolute px companion -- a tall card whose trailing
    void is large in mm but one point under the 10% ratio bar.

Participation in TRACK-MISALIGN is by explicit contract (>=2 direct
children classed ``.track``, confirmed as one visual row), so the negative
cases pin down that arbitrary horizontal rows -- keybox-style tile grids,
wrapped "rows" -- are never judged.

Skipped when Playwright/Chromium isn't installed.
"""
from __future__ import annotations

import argparse
import base64
import io

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


def _args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200,
        mathjax_timeout_ms=5000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, tall_min_ratio=0.36, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10,
        strict=False,
    )


# Six cards exercise the TRACK-MISALIGN branches:
#   * card A (.two-track): left track a tall painted block, right track one
#     short paragraph -> ~300 px foot void -> MUST flag, naming the short
#     track by full class and left-to-right ordinal;
#   * card B (.two-track balanced): two equal painted blocks -> MUST NOT
#     flag;
#   * card C (keybox-style tile grid, NO .track classes): wildly unequal
#     tile heights -> not under the contract, MUST NOT even be collected;
#   * card D (flex-wrap "tracks"): two 60%-wide .track children forced onto
#     two stacked rows -> the flex row/nowrap precondition fails -> skipped;
#   * card E (2-column grid, FOUR .track children): the grid wraps them
#     onto two rows -> the top-alignment confirmation fails -> skipped
#     (comparing bottoms across stacked rows is meaningless);
#   * card F (two .track children stacked in the SAME grid cell): tops
#     align but the horizontal spans coincide -> the horizontal-distinct
#     confirmation fails -> skipped.
_HTML_TRACKS = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .card { background: #fff; border: 2px solid #888; padding: 14px;
          font-size: 18px; line-height: 1.35; margin-bottom: 40px; }
  .two-track { display: grid; grid-template-columns: 2fr 1fr; gap: 16px;
               align-items: start; }
  .tile-row { display: grid; grid-template-columns: repeat(3, 1fr);
              gap: 8px; }
  .wrap-row { display: flex; flex-wrap: wrap; gap: 12px; }
  .wrap-row .track { flex: 0 0 60%; }
  .grid-two-rows { display: grid; grid-template-columns: 1fr 1fr;
                   gap: 12px; align-items: start; }
  .stacked-cell { display: grid; grid-template-columns: 1fr; }
  .stacked-cell .track { grid-area: 1 / 1; }
  .block { background: #ccd; }
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card misaligned" data-measure-role="card">
      <div class="two-track">
        <div class="track"><div class="block" style="height:400px">Tall
          figure stand-in filling the left track completely.</div></div>
        <div class="track chips"><p>One short paragraph only.</p></div>
      </div>
    </div>
    <div class="card balanced" data-measure-role="card">
      <div class="two-track">
        <div class="track"><div class="block" style="height:300px">Left
          block.</div></div>
        <div class="track"><div class="block" style="height:300px">Right
          block.</div></div>
      </div>
    </div>
    <div class="card tiles" data-measure-role="card">
      <div class="tile-row">
        <div class="block" style="height:220px">Tall tile.</div>
        <div class="block" style="height:60px">Short tile.</div>
        <div class="block" style="height:220px">Tall tile.</div>
      </div>
      <p>A closing line so the card hugs its own content bottom.</p>
    </div>
    <div class="card wrapped" data-measure-role="card">
      <div class="wrap-row">
        <div class="track"><div class="block" style="height:200px">First
          wrapped track.</div></div>
        <div class="track"><p>Second track, forced onto the next row.</p>
        </div>
      </div>
    </div>
    <div class="card gridrows" data-measure-role="card">
      <div class="grid-two-rows">
        <div class="track"><div class="block" style="height:180px">Row one
          left.</div></div>
        <div class="track"><div class="block" style="height:180px">Row one
          right.</div></div>
        <div class="track"><p>Row two left, much shorter.</p></div>
        <div class="track"><div class="block" style="height:180px">Row two
          right.</div></div>
      </div>
    </div>
    <div class="card overlap" data-measure-role="card">
      <div class="stacked-cell">
        <div class="track"><div class="block" style="height:240px">Tall
          layer in the shared cell.</div></div>
        <div class="track"><p>Short layer sharing the same cell.</p></div>
      </div>
    </div>
  </div>
  </div>
</body></html>
"""


def test_track_misalign_contract_and_geometry(tmp_path, capsys) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_HTML_TRACKS, encoding="utf-8")

    rc = _polish.cmd_polish(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 0
    # Only cards A and B are collected: the tile grid carries no .track
    # (contract); the wrap-row fails the flex nowrap precondition; the
    # 2x2 grid fails top alignment; the shared-cell pair fails the
    # horizontal-distinct confirmation.
    assert "side-by-side tracks : 2" in combined
    # Exactly one warning -- card A, naming the short track by full class
    # list and left-to-right ordinal.
    assert combined.count("CARD/TRACK-MISALIGN") == 1
    assert "card misaligned" in combined
    assert "#2 of 2 left-to-right" in combined
    assert "<div.track.chips>" in combined
    assert "card balanced" not in combined
    assert "card tiles" not in combined
    assert "card wrapped" not in combined
    assert "card gridrows" not in combined
    assert "card overlap" not in combined


def _png_data_uri(w: int, h: int) -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 60, 60)).save(buf, format="PNG")
    return ("data:image/png;base64,"
            + base64.b64encode(buf.getvalue()).decode("ascii"))


# Two crop-lock groups plus label hygiene:
#   * group "qual" mirrors the real defect at natural scale -- 620x399 vs
#     620x392, a 1.8% AR mismatch -> MUST flag, identified by asset id;
#   * group "ok" is the same crop box twice -> MUST NOT flag;
#   * both images render small in a wide card, so FIG/WIDE fires -- and must
#     print the asset id / a stub, never the raw base64 payload.
_HTML_PAIRS_HEAD = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  .card { border: 2px solid #888; padding: 14px; }
  .card img { width: 30%; }
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">
"""
_HTML_PAIRS_TAIL = """
    </div>
  </div>
  </div>
</body></html>
"""


def test_pair_geometry_and_fig_labels(tmp_path, capsys) -> None:
    pytest.importorskip("PIL")
    imgs = (
        f'<img src="{_png_data_uri(620, 399)}" data-asset-id="qual_a" '
        f'data-crop-lock="qual">'
        f'<img src="{_png_data_uri(620, 392)}" data-asset-id="qual_b" '
        f'data-crop-lock="qual">'
        f'<img src="{_png_data_uri(400, 260)}" data-crop-lock="ok">'
        f'<img src="{_png_data_uri(400, 260)}" data-crop-lock="ok">'
    )
    poster = tmp_path / "poster.html"
    poster.write_text(_HTML_PAIRS_HEAD + imgs + _HTML_PAIRS_TAIL,
                      encoding="utf-8")

    rc = _polish.cmd_polish(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 0
    assert "crop-lock images    : 4" in combined
    # The mismatched group flags once, by asset id; the identical one is
    # silent.
    assert combined.count("FIG/PAIR-GEOMETRY") == 1
    assert "crop-lock group 'qual'" in combined
    assert "qual_a" in combined and "qual_b" in combined
    assert "'ok'" not in combined
    # Label hygiene: the wide-AR figures at 30% width fire FIG/WIDE, whose
    # label must be the asset id (when present) or the data-URI stub --
    # never the base64 payload (a real report once drowned in a ~500k-char
    # URI).
    assert "FIG/WIDE: 'qual_a'" in combined
    assert "FIG/WIDE: '<inline data URI," in combined  # the id-less pair
    assert "iVBOR" not in combined


# One tagged card with a fixed height and a short paragraph: trailing is
# ~90 px = ~7.5% of the 1200 px card -- under the 10% ratio, over the 60 px
# absolute companion -> MUST flag. A second card at ~40 px trailing stays
# under both bars -> MUST NOT flag.
_HTML_TRAILING = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-size: 18px; line-height: 1.35; font-family: Georgia, serif; }
  .card { border: 2px solid #888; padding: 14px; margin-bottom: 40px; }
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card deep" data-measure-role="card" style="height:1200px">
      <div style="height:1080px; background:#ccd">Content block.</div>
    </div>
    <div class="card ok" data-measure-role="card" style="height:1200px">
      <div style="height:1130px; background:#ccd">Content block.</div>
    </div>
  </div>
  </div>
</body></html>
"""


def test_card_trailing_absolute_floor(tmp_path, capsys) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_HTML_TRAILING, encoding="utf-8")

    rc = _polish.cmd_polish(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 0
    # card 0: ~90 px trailing at ~7.5% -- ratio alone stayed silent before,
    # the absolute companion catches it. card 1: ~40 px, under both bars.
    assert combined.count("CARD/TRAILING") == 1
    assert "CARD/TRAILING: card 0" in combined
