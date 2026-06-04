"""Chromium-gated integration tests for the intra-column whitespace gate
in ``measure``.

Real-world failure this pins (Paper2Poster pilot, 2026-06-04): an agent
hit the column-bottom spread gate by setting ``justify-content:
space-between`` on under-filled columns -- the first card pins to the
top, the last card pins to the bottom, spread reads 0.00 px, the
footer gap lands in band, and measure PASSes while a 98-135 px void sits
mid-column (design row-gap was 22.7 px). polish's space-between check is
a SOFT warn with a relative threshold (5% of column height ~= 117 px on
a 36in poster), so it stayed silent too. The void is plainly visible in
print; a human caught it, the gates did not.

The fix: measure hard-fails when the gap between consecutive stacked
cards (after grouping side-by-side cards into rows) exceeds
``--max-intercard-gap`` (default 50 px, same ceiling as the footer gap).

Verifies the gate FIRES on the space-between void, does NOT fire on a
normally-flowed column with design-sized gaps, and does NOT false-fire
on side-by-side cards sharing a row.

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


# Full-bleed 24x36in poster (viewport 2304x3456 px at 96 ppi), one flex
# column, two fixed-height cards that together under-fill the column.
# `justify_css` is the only variable: space-between stretches the slack
# into a mid-column void; normal flow + flex-grow on the last card fills
# the column with content instead. The footer-strip's 40 px margin keeps
# the footer gap in band either way, so the new gate is what the
# assertions isolate.
def _poster(justify_css: str, grow_last: bool) -> str:
    grow = "flex-grow: 1;" if grow_last else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: flex; flex-direction: column; padding: 60px; }}
  .column {{ flex: 1; display: flex; flex-direction: column;
             gap: 24px; {justify_css} }}
  .card {{ border: 2px solid #888; padding: 20px; height: 1200px; }}
  .card.last {{ {grow} }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233; }}
  p {{ font-size: 28px; line-height: 1.4; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card"><p>Card one.</p></div>
      <div class="card last" data-measure-role="card"><p>Card two.</p></div>
    </div>
    <div class="footer-strip" data-measure-role="footer-strip"></div>
  </div>
</body></html>
"""


# Same canvas, one column whose first "row" is two half-width cards side
# by side (a row wrapper WITHOUT a measure role, so both cards map to the
# column) followed by a full-width card. Vertical-overlap grouping must
# treat the pair as ONE row: the only inter-row gaps are the design 24 px,
# so the gate must stay silent.
_SIDE_BY_SIDE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; background: #fff; }
  .poster { width: 24in; height: 36in; background: #fff;
            display: flex; flex-direction: column; padding: 60px; }
  .column { flex: 1; display: flex; flex-direction: column; gap: 24px; }
  .row { display: flex; gap: 24px; }
  .row .card { flex: 1; height: 900px; }
  .card { border: 2px solid #888; padding: 20px; }
  .card.wide { flex-grow: 1; }
  .footer-strip { height: 160px; margin-top: 40px; background: #233; }
  p { font-size: 28px; line-height: 1.4; }
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="column" data-measure-role="column">
      <div class="row">
        <div class="card" data-measure-role="card"><p>Left.</p></div>
        <div class="card" data-measure-role="card"><p>Right.</p></div>
      </div>
      <div class="card wide" data-measure-role="card"><p>Below.</p></div>
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
        position_tol_px=2.0, max_clip_px=2.0,
        max_intercard_gap=50.0, min_intercard_gap=12.0, json_out=None,
    )


def _run(tmp_path, capsys, html: str):
    poster = tmp_path / "poster.html"
    poster.write_text(html, encoding="utf-8")
    rc = _measure.cmd_measure(_args(poster))
    return rc, "".join(capsys.readouterr())


def test_space_between_void_fires(tmp_path, capsys) -> None:
    # Two 1200 px cards in a ~3296 px column with space-between -> a
    # ~700-900 px mid-column void while spread = 0 and the footer gap is
    # in band. The gate must hard-fail and tell the author to fill the
    # slack with content, not stretched whitespace.
    rc, out = _run(
        tmp_path, capsys,
        _poster("justify-content: space-between;", grow_last=False),
    )
    assert rc == 1
    assert "intercard" in out or "between stacked cards" in out
    assert "space-between" in out  # the fix hint names the culprit


def test_filled_column_passes(tmp_path, capsys) -> None:
    # Same two cards, normal flow, last card flex-grows to absorb the
    # slack -> the only inter-card gap is the design 24 px. PASS, and no
    # intercard complaint.
    rc, out = _run(tmp_path, capsys, _poster("", grow_last=True))
    assert rc == 0
    assert "PASS" in out
    assert "between stacked cards" not in out


def test_side_by_side_cards_no_false_positive(tmp_path, capsys) -> None:
    # Two cards sharing a row must be grouped as one row, not read as a
    # negative/huge "gap" pair; the column's real inter-row gap is 24 px.
    rc, out = _run(tmp_path, capsys, _SIDE_BY_SIDE)
    assert rc == 0
    assert "between stacked cards" not in out


def test_cards_too_tight_fires(tmp_path, capsys) -> None:
    # The flip side of the void: cards nearly touching. The shipped card
    # shadow is `0 2u 6u` (offset ~7.6 px + blur ~22.7 px in print), so a
    # gap under ~12 px buries the shadow core under the next card and the
    # stack reads as one fused slab. Two cards at a 4 px gap (the second
    # flex-grows so the footer gap stays in band) must hard-fail with the
    # shadow rationale.
    html = _poster("", grow_last=True).replace("gap: 24px;", "gap: 4px;")
    rc, out = _run(tmp_path, capsys, html)
    assert rc == 1
    assert "too tight" in out
    assert "shadow" in out


def test_intercard_gaps_row_grouping_pure() -> None:
    # Pure-function check (no Chromium): side-by-side cards chain into one
    # row; gaps are measured between row bands.
    cards = [
        {"y": 0.0, "bottom": 900.0},     # row 1, left
        {"y": 0.0, "bottom": 880.0},     # row 1, right (shorter)
        {"y": 924.0, "bottom": 1800.0},  # row 2 -> gap 24 from row1 max
        {"y": 1922.0, "bottom": 2400.0},  # row 3 -> gap 122 (the void)
    ]
    gaps = _measure.intercard_gaps(cards)
    assert [round(g, 1) for g in gaps] == [24.0, 122.0]
