"""Chromium-gated integration test for the prose-WIDOW geometry inside
``polish``'s ``_POLISH_JS`` (section 8).

The mocked unit tests in ``test_polish_output.py`` feed the Python loop a
canned ``widows`` list and never run the JS, so the detection itself --
``<br>``-segment splitting, per-token ``Range`` measurement, NBSP-as-
separator tokenising, zero-width wrap-space filtering, and visual-line
grouping -- is only exercised here against a real headless Chromium.

Determinism: each "must flag" case ends in a word LONGER than the callout
width, so it cannot share a line and is stranded alone regardless of small
font-metric differences across machines (the same robustness trick the
shipped card-trailing integration test relies on). Skipped when Playwright
/ Chromium isn't installed.
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


# Callout width is pinned narrow; each "must flag" case ends in a word wider
# than that width, so it is forced alone onto the last visual line.
_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .card { padding: 10px; }
  .callout, .caption { width: 240px; font-size: 30px; line-height: 1.3; }
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">
      <!-- A: long final word can't share a line -> stranded alone -> WIDOW. -->
      <div class="callout" id="a">alpha beta supercalifragilisticword.</div>
      <!-- B: &nbsp;-glued multiword tail -> last line is >1 token -> NO widow
           (the recommended Gate B fix must not re-trip the gate). -->
      <div class="callout" id="b">Diffusion policies are expressive but their&nbsp;likelihood&nbsp;is&nbsp;intractable.</div>
      <!-- C: a single word total -> can't widow -> NO widow. -->
      <div class="callout" id="c">Short.</div>
      <!-- D: widow lives in the FIRST <br> segment, NOT the block's last
           visual line (the original incident shape). Second segment is one
           token so it is skipped. -->
      <div class="callout" id="d">alpha beta antidisestablishmentword.<br><strong>Done.</strong></div>
      <!-- E: trailing inline <svg> -> the opaque cell lands on/after the last
           text line, so the last judged line is not pure text -> NO widow.
           (Pre-incident behavior skipped the whole block; same verdict here,
           different mechanism.) -->
      <div class="callout" id="e">alpha beta skipmelongwordplease.<svg width="12" height="12"></svg></div>
      <!-- F: regression for the eb181286 "one." incident -- inline math EARLY
           in the text must NOT hide a pure-text lone last word. -->
      <div class="callout" id="f">draw <mjx-container>K</mjx-container> actions and pick strandedregressionword.</div>
      <!-- G: a .caption between 220 and 400 chars -- the old 220-char cap hid
           the incident caption (231 chars); display text now caps at 400. -->
      <div class="caption" id="g">The quick brown fox jumps over the lazy dog near the river
           bank while the camera records every motion frame for later offline
           analysis and careful manual review of all seven dynamic environments
           considered in the study finalstrandedcaptionword.</div>
      <!-- H: TALL opaque cells (display math) must not inflate the line-group
           tolerance and merge the stranded text line away (Codex MAJOR-1). -->
      <div class="callout" id="h">alpha
           <mjx-container style="display:inline-block;width:10px;height:500px"></mjx-container>
           <mjx-container style="display:inline-block;width:10px;height:500px"></mjx-container>
           <mjx-container style="display:inline-block;width:10px;height:500px"></mjx-container>
           <mjx-container style="display:inline-block;width:10px;height:500px"></mjx-container>
           beta tallmathstrandedword.</div>
      <!-- I: a <br> INSIDE a table cell must not split the OUTER prose into
           segments and orphan the trailing word (Codex MAJOR-2). -->
      <div class="callout" id="i">alpha
           <table style="display:inline-table;width:20px;height:20px"><tr><td>x<br>y</td></tr></table>
           tableinnerbrstrandedword.</div>
      <!-- J: a visibility:hidden trailing opaque paints nothing -- the lone
           word IS visually stranded and must still flag (Codex MAJOR-3). -->
      <div class="callout" id="j">alpha beta hiddensvgstrandedword.<svg style="visibility:hidden" width="12" height="12"></svg></div>
      <!-- K: UNSPACED opaques fuse the surrounding text into one token; the
           token's Range must not smuggle the tall opaque rects in as TEXT
           cells and re-inflate the tolerance (Codex round-2 MAJOR). -->
      <div class="callout" id="k">alpha<mjx-container style="display:inline-block;width:10px;height:500px;vertical-align:middle"></mjx-container><mjx-container style="display:inline-block;width:10px;height:500px;vertical-align:middle"></mjx-container><mjx-container style="display:inline-block;width:10px;height:500px;vertical-align:middle"></mjx-container><mjx-container style="display:inline-block;width:10px;height:500px;vertical-align:middle"></mjx-container>beta unspacedmathstrandedword.</div>
    </div>
  </div>
  </div>
</body></html>
"""


def _args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200,
        mathjax_timeout_ms=5000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, tall_min_ratio=0.36, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10, strict=False,
    )


def test_widow_geometry_end_to_end(tmp_path, capsys) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_HTML, encoding="utf-8")

    rc = _polish.cmd_polish(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 0                                  # soft gate, warn-only
    # A (real widow), D (first-segment widow), F (math early in text),
    # G (caption in the 220-400 char band), H (tall opaque vs tolerance),
    # I (<br> inside table), J (hidden trailing svg), K (unspaced-math token
    # Range) flag; B/C/E do not.
    assert "prose widows        : 8" in combined
    assert "supercalifragilisticword." in combined       # A
    assert "antidisestablishmentword." in combined       # D first segment
    # B: an &nbsp;-glued tail is multi-token -> must NOT flag.
    assert "intractable." not in combined
    # E: opaque <svg> sits on/after the last text line -> not judgeable -> no flag.
    assert "skipmelongwordplease." not in combined
    # F: inline math EARLY must not hide a pure-text lone last word (the
    # eb181286 "one." incident).
    assert "strandedregressionword." in combined
    # G: display-text cap is 400, not 220 -- the long caption is measured.
    assert "finalstrandedcaptionword." in combined
    # H/I/J/K: Codex-audit regressions (tolerance skew / inner <br> /
    # hidden svg / unspaced-math token Range).
    assert "tallmathstrandedword." in combined
    assert "tableinnerbrstrandedword." in combined
    assert "hiddensvgstrandedword." in combined
    assert "unspacedmathstrandedword." in combined
