"""Chromium-gated integration test for the prose-WIDOW geometry inside
``polish``'s ``_POLISH_JS`` (section 8).

The mocked unit tests in ``test_polish_output.py`` feed the Python loop a
canned ``widows`` list and never run the JS, so the detection itself --
``<br>``-segment splitting, per-token ``Range`` measurement, NBSP-as-
separator tokenising, zero-width wrap-space filtering, visual-line grouping,
and the WIDTH-based runt test -- is only exercised here against a real
headless Chromium.

Determinism: the gate now flags by the last line's WIDTH (a last line filling
< 30% of the widest line is a stranded runt), NOT by word count. So the "must
flag" cases end with a word LONGER than the callout placed SECOND-TO-LAST: it
overflows its line and forces a SHORT final marker onto a line of its own,
where the marker fills a tiny fraction of the (penult-width) measure regardless
of small font-metric differences across machines. The "must not flag" cases
either fill the last line (a single long word, a wide glued tail) or carry an
opaque cell on the last line. Skipped when Playwright / Chromium isn't installed.
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


# The callout/caption width is pinned narrow. A 38-char word is far wider than
# that, so wherever it sits it (a) overflows onto a line of its own and (b)
# pushes whatever follows onto the NEXT line. Used SECOND-TO-LAST, it strands a
# short final marker that fills a tiny fraction of the measure -> WIDOW.
_PEN = "supercalifragilisticexpialidociousword."
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
      <!-- A: long penult strands a SHORT final marker -> tiny last line -> WIDOW. -->
      <div class="callout" id="a">alpha beta __PEN__ flagA.</div>
      <!-- B: the recommended fix -- &nbsp; glues the marker UP to the wide
           penult so the last line is wide -> NO widow (same shape as A, space
           replaced by &nbsp;). -->
      <div class="callout" id="b">alpha beta __PEN__&nbsp;noflagB.</div>
      <!-- C: a single word total -> can't wrap -> NO widow. -->
      <div class="callout" id="c">Short.</div>
      <!-- D: widow lives in the FIRST <br> segment, NOT the block's last visual
           line (the original incident shape). Second segment is one token so it
           is skipped. -->
      <div class="callout" id="d">alpha __PEN__ flagD.<br><strong>Done.</strong></div>
      <!-- E: trailing inline <svg> (VISIBLE) lands on the last line -> the last
           line carries an opaque cell -> not judgeable -> NO widow. -->
      <div class="callout" id="e">alpha __PEN__ flagE.<svg width="12" height="12"></svg></div>
      <!-- F: regression for the eb181286 "one." incident -- inline math EARLY
           in the text must NOT hide a pure-text stranded last line. -->
      <div class="callout" id="f">draw <mjx-container>K</mjx-container> actions __PEN__ flagF.</div>
      <!-- G: a .caption in the 220-400 char band -- the old 220-char cap hid
           the incident caption (231 chars); display text now caps at 400. -->
      <div class="caption" id="g">The quick brown fox jumps over the lazy dog near the river
           bank while the camera records every motion frame for later offline
           analysis and careful manual review of all seven dynamic environments
           considered in the study __PEN__ flagG.</div>
      <!-- H: TALL opaque cells (display math) must not inflate the line-group
           tolerance and merge the stranded line away (Codex MAJOR-1). -->
      <div class="callout" id="h">alpha
           <mjx-container style="display:inline-block;width:10px;height:500px"></mjx-container>
           <mjx-container style="display:inline-block;width:10px;height:500px"></mjx-container>
           <mjx-container style="display:inline-block;width:10px;height:500px"></mjx-container>
           <mjx-container style="display:inline-block;width:10px;height:500px"></mjx-container>
           beta __PEN__ flagH.</div>
      <!-- I: a <br> INSIDE a table cell must not split the OUTER prose into
           segments and orphan the trailing word (Codex MAJOR-2). -->
      <div class="callout" id="i">alpha
           <table style="display:inline-table;width:20px;height:20px"><tr><td>x<br>y</td></tr></table>
           __PEN__ flagI.</div>
      <!-- J: a visibility:hidden trailing opaque paints nothing and is NOT
           recorded as a cell -- the last line stays pure text, so the short
           marker IS a stranded runt and must still flag (Codex MAJOR-3). -->
      <div class="callout" id="j">alpha __PEN__ flagJ.<svg style="visibility:hidden" width="12" height="12"></svg></div>
      <!-- K: UNSPACED opaques fuse the surrounding text into one token; the
           token's Range must not smuggle the tall opaque rects in as TEXT
           cells and re-inflate the tolerance (Codex round-2 MAJOR). -->
      <div class="callout" id="k">alpha<mjx-container style="display:inline-block;width:10px;height:500px;vertical-align:middle"></mjx-container><mjx-container style="display:inline-block;width:10px;height:500px;vertical-align:middle"></mjx-container><mjx-container style="display:inline-block;width:10px;height:500px;vertical-align:middle"></mjx-container><mjx-container style="display:inline-block;width:10px;height:500px;vertical-align:middle"></mjx-container>beta __PEN__ flagK.</div>
      <!-- L: a SHORT TWO-word last line is still a runt by WIDTH -- the old
           word-count rule missed this; the width rule must flag it. -->
      <div class="callout" id="l">alpha __PEN__ is L2.</div>
      <!-- M: a SINGLE LONG word as the last line FILLS the measure (width ~=
           the widest line) -> NOT stranded -> NO widow. The old word-count rule
           wrongly flagged this; the width rule must clear it. -->
      <div class="callout" id="m">alpha beta solitarylongwordfillingtheentirelinewidth.</div>
      <!-- N: a WIDE inline opaque (600px svg) on an earlier line must NOT
           inflate the measure -- the text last line fills the TEXT measure and
           is not a runt. With the buggy all-cell measure (600px) the last line
           reads as 18% and false-warns; with the text-only measure it is 100%
           and clears (Codex MAJOR). -->
      <div class="callout" id="n">tiny text <svg width="600" height="10"></svg> noflagN.</div>
      <!-- O: a gallery-strip--vrail rail title is a DELIBERATELY narrow stacked
           column (each word on its own horizontal line, an over-long word broken
           with a soft hyphen). Its short last line is intentional, so it carries
           data-vrail-title to opt out of the widow check. Uses .section-title
           (which IS in the gate's selector) at the same narrow width that makes
           case A flag, so this shape WOULD runt without the attribute -- the test
           pins the attribute skip, not mere selector non-membership. -->
      <div class="section-title" id="o" data-vrail-title style="width: 240px">alpha __PEN__ vskip.</div>
    </div>
  </div>
  </div>
</body></html>
""".replace("__PEN__", _PEN)


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
    # Flag: A (basic runt), D (first-segment runt), F (math early), G (caption
    # in the 220-400 band), H (tall opaque vs tolerance), I (<br> inside table),
    # J (hidden trailing svg stays pure text), K (unspaced-math token Range),
    # L (short TWO-word last line). Nine in all.
    assert "prose widows        : 9" in combined
    assert "flagA." in combined                            # A
    assert "flagD." in combined                            # D first segment
    assert "flagF." in combined                            # F math early
    assert "flagG." in combined                            # G caption cap 400
    assert "flagH." in combined                            # H tall opaque
    assert "flagI." in combined                            # I <br> in table
    assert "flagJ." in combined                            # J hidden svg
    assert "flagK." in combined                            # K unspaced math
    assert "is L2." in combined                            # L two-word runt
    # Do NOT flag:
    # B: &nbsp; glues the marker to the wide penult -> wide last line.
    assert "noflagB." not in combined
    # E: a VISIBLE opaque on the last line -> not judgeable.
    assert "flagE." not in combined
    # M: a single long word fills the line (width ~= measure) -> not stranded.
    assert "solitarylongword" not in combined
    # N: a wide inline opaque must not inflate the measure -> the text last line
    # fills the TEXT measure and is not a runt (guards the Codex MAJOR fix).
    assert "noflagN." not in combined
    # O: a gallery-strip--vrail rail title marked data-vrail-title is exempt -> a
    # deliberately narrow stacked title is not a runt. Pins the data-vrail-title
    # skip (same narrow shape as case A, which DOES flag, minus the attribute).
    assert "vskip." not in combined
