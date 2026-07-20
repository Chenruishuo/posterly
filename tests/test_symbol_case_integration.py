"""Chromium-gated integration test for the SYMBOL-CASE scan in
``polish``'s ``_POLISH_JS``.

Lowercase Greek under a computed ``text-transform: uppercase`` paints as
its capital (``α`` -> ``Α``, a Latin-A lookalike), so the scan must flag
exactly the rendered, transformed runs — including one that merely
INHERITS the transform through a plain ``<span>``, the micro sign
(U+00B5 → a Latin-M-lookalike capital Mu), Greek Extended, a
``visibility:visible`` child restoring paint inside a hidden ancestor,
a ``display:contents`` parent (no box of its own, text paints anyway —
including under ``opacity:0``, which does not apply to boxless nodes),
and transparent ink that still paints via an opaque ``text-shadow`` or
``-webkit-text-stroke`` — and stay silent for: the ``.tt-none``
escape-hatch span, untransformed Greek, Latin-only uppercase runs,
unpainted runs (``display:none`` / ``visibility:hidden`` — including
inherited into ``display:contents`` — / ancestor ``opacity:0`` /
``font-size:0`` / transparent ink whose shadow and stroke are absent or
themselves transparent), ``capitalize`` (out of scope:
only ``uppercase`` remaps a mid-word symbol), and MathJax's
screen-reader-only ``mjx-assistive-mml`` mirror. Accepted probe
limitation (documented in the scan): text clipped away by an ancestor's
``height:0 + overflow:hidden`` still counts as painted — the Step-5
render eyeball owns that tail. The mocked
unit tests in ``test_polish_output.py`` feed the Python loop canned
``symbolCase`` entries and never run the JS, so the detection itself is
only exercised here. Skipped when Playwright / Chromium isn't installed.
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


_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .card { padding: 10px; }
  .uc { text-transform: uppercase; white-space: nowrap; }
  .cap { text-transform: capitalize; white-space: nowrap; }
  .tt-none { text-transform: none; }
  .hidden { display: none; }
  .vhid { visibility: hidden; }
  .vis { visibility: visible; }
  .op0 { opacity: 0; }
  .fs0 { font-size: 0; }
  .tink { color: transparent; }
  .tsh { color: transparent; text-shadow: 0 0 2px #000; }
  .dc { display: contents; }
  .tsh0 { color: transparent; text-shadow: 0 0 2px rgba(0,0,0,0); }
  .tst0 { color: transparent; -webkit-text-stroke: 1px transparent; }
  .tstk { color: transparent; -webkit-text-stroke: 1px #000; }
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">
      <!-- A: Greek directly inside an uppercased element -> FLAG. -->
      <div class="uc flagA">flagA α &gt; 1</div>
      <!-- B: the escape hatch -- the symbol sits in a .tt-none span, the
           rest of the run is Latin -> NO flag anywhere in this element. -->
      <div class="uc noflagB">noflagB <span class="tt-none">α</span> = 4</div>
      <!-- C: Greek with no transform -> NO flag. -->
      <div class="noflagC">noflagC α = 4</div>
      <!-- D: uppercased but Latin-only -> NO flag. -->
      <div class="uc noflagD">noflagD sharpen</div>
      <!-- E: uppercased Greek in an UNPAINTED subtree -> NO flag. -->
      <div class="uc hidden noflagE">noflagE α</div>
      <!-- F: MathJax's screen-reader-only MML mirror -> NO flag. -->
      <div class="uc noflagF">noflagF
        <mjx-assistive-mml>α</mjx-assistive-mml></div>
      <!-- G: capitalize is out of scope (only uppercase remaps a mid-word
           symbol) -> NO flag. -->
      <div class="cap noflagG">noflagG α</div>
      <!-- H: the transform INHERITED through a plain span -> FLAG (the
           text node's parent is the span; its computed transform is
           uppercase). -->
      <div class="uc"><span class="flagH">flagH α of 2</span></div>
      <!-- I: visibility:hidden paints nothing (boxes exist, chain does
           not) -> NO flag (pins the visibleIn walk). -->
      <div class="uc vhid noflagI">noflagI α</div>
      <!-- J: opacity:0 on an ANCESTOR paints nothing -> NO flag. -->
      <div class="op0"><div class="uc noflagJ">noflagJ α</div></div>
      <!-- K: font-size:0 collapses every Range rect to zero -> NO flag
           (pins the non-zero-box requirement). -->
      <div class="uc fs0 noflagK">noflagK α</div>
      <!-- L: the micro sign U+00B5 uppercases to a Latin-M-lookalike
           capital Mu ("5 µs" paints as "5 MS") -> FLAG. -->
      <div class="uc flagL">flagL 5 µs window</div>
      <!-- M: Greek Extended (U+1F00 block) also case-shifts -> FLAG
           (pins the script-wide regex; the old narrow class missed it). -->
      <div class="uc flagM">flagM ἄ form</div>
      <!-- N: a visibility:visible child RESTORES paint inside a hidden
           ancestor -> FLAG (pins the used-value judgment; a blanket
           ancestor walk would wrongly skip it). -->
      <div class="vhid"><span class="uc vis flagN">flagN α</span></div>
      <!-- O: transparent ink with no shadow/stroke paints nothing ->
           NO flag. -->
      <div class="uc tink noflagO">noflagO α</div>
      <!-- P: transparent ink BUT a text-shadow still paints the glyph
           shape -> FLAG (pins the shadow guard on the ink skip). -->
      <div class="uc tsh flagP">flagP α</div>
      <!-- Q: a display:contents parent has NO box of its own but its text
           paints -> FLAG (pins the manual path; checkVisibility() would
           wrongly report it invisible). -->
      <div class="uc"><div class="dc flagQ">flagQ α</div></div>
      <!-- R: display:contents INHERITING hidden from an ancestor -> the
           manual path reads the used visibility -> NO flag. -->
      <div class="vhid"><div class="dc uc noflagR">noflagR α</div></div>
      <!-- S: transparent ink + TRANSPARENT shadow paints nothing ->
           NO flag (pins the shadow COLOR check, not mere presence). -->
      <div class="uc tsh0 noflagS">noflagS α</div>
      <!-- T: transparent ink + TRANSPARENT stroke paints nothing ->
           NO flag (pins the stroke COLOR check). -->
      <div class="uc tst0 noflagT">noflagT α</div>
      <!-- U: transparent ink BUT an opaque stroke draws the outline ->
           FLAG. -->
      <div class="uc tstk flagU">flagU α</div>
      <!-- V: opacity:0 ON a boxless display:contents element does NOT
           apply -- its direct text paints -> FLAG (pins the walk
           skipping boxless nodes). -->
      <div class="dc op0 uc flagV">flagV α</div>
      <!-- W: a BOXED child under a display:contents opacity:0 ancestor
           paints too -> FLAG (pins the contents-on-chain routing away
           from checkVisibility, which wrongly reports it hidden). -->
      <div class="dc op0"><div class="uc flagW">flagW α</div></div>
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


def test_symbol_case_end_to_end(tmp_path, capsys) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_HTML, encoding="utf-8")

    rc = _polish.cmd_polish(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 0                                  # soft gate, warn-only
    combined.encode("ascii")                        # Greek ships escaped
    assert "case-corrupt runs   : 10" in combined   # A,H,L,M,N,P,Q,U,V,W
    assert "flagA" in combined
    assert "flagH" in combined
    assert "flagL" in combined                      # micro sign U+00B5
    assert "flagM" in combined                      # Greek Extended
    assert "flagN" in combined                      # restored visibility
    assert "flagP" in combined                      # transparent + shadow
    assert "flagQ" in combined                      # display:contents parent
    assert "flagU" in combined                      # transparent + stroke
    assert "flagV" in combined                      # contents + own opacity:0
    assert "flagW" in combined                      # boxed child under both
    assert "noflagB" not in combined
    assert "noflagC" not in combined
    assert "noflagD" not in combined
    assert "noflagE" not in combined
    assert "noflagF" not in combined
    assert "noflagG" not in combined
    assert "noflagI" not in combined                # visibility:hidden
    assert "noflagJ" not in combined                # ancestor opacity:0
    assert "noflagK" not in combined                # font-size:0
    assert "noflagO" not in combined                # transparent ink
    assert "noflagR" not in combined                # display:contents, hidden
    assert "noflagS" not in combined                # transparent shadow
    assert "noflagT" not in combined                # transparent stroke
