"""Chromium-gated integration test for measure's failure report rework:
the shared passing band + per-column safe deltas and the edit-targets
block (source lines + math-stripped anchors) on a real failing poster.

Skipped when Playwright / Chromium isn't installed.
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


# Two columns with clearly different bottoms -> spread failure. The
# section titles give the anchors; card heights are fixed so the
# shorter column needs a directed grow.
_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; background: #fff; }
  .poster { width: 24in; height: 36in; background: #fff;
            display: flex; flex-direction: column; padding: 60px; }
  .body { flex: 1; display: flex; gap: 24px; }
  .column { flex: 1; display: flex; flex-direction: column; gap: 24px; }
  .card { border: 2px solid #888; padding: 20px; }
  .footer-strip { height: 160px; margin-top: 40px; background: #233; }
  p { font-size: 28px; line-height: 1.4; }
  .section-title { font-weight: 700; font-size: 34px; }
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="body">
      <div class="column" data-measure-role="column">
        <div class="card" data-measure-role="card" style="height: 2900px">
          <div class="section-title">1 Motivation</div><p>Left.</p>
        </div>
      </div>
      <div class="column" data-measure-role="column">
        <div class="card" data-measure-role="card" style="height: 1400px">
          <div class="section-title">2 Method</div><p>Right top.</p>
        </div>
        <div class="card" data-measure-role="card" style="height: 1200px">
          <div class="section-title">3 Results</div><p>Right bottom.</p>
        </div>
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
        position_tol_px=2.0, max_clip_px=2.0,
        max_intercard_gap=1e9,  # isolate the spread/gap failure
        min_intercard_gap=0.0,
        json_out=None, measure_budget=0,
    )


def test_failure_report_carries_band_and_targets(
    tmp_path, capsys
) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_HTML, encoding="utf-8")
    rc = _measure.cmd_measure(_args(poster))
    combined = "".join(capsys.readouterr())

    assert rc == 1
    assert "shared passing band:" in combined
    assert "[safe " in combined            # per-column safe delta range
    assert "[measure] edit targets" in combined
    # Anchors: section-title text, and all three cards listed.
    for anchor in ("1 Motivation", "2 Method", "3 Results"):
        assert anchor in combined
    # Source lines resolved (no fallback L?).
    assert "L?" not in combined
    # Exactly one bottom marker per column (no sub-pixel ties here).
    assert combined.count("<- bottom card") == 2
    # Line numbers point at real card tags in the source.
    src_lines = poster.read_text(encoding="utf-8").splitlines()
    import re

    for m in re.finditer(r"L(\d+)", combined):
        line = src_lines[int(m.group(1)) - 1]
        assert 'data-measure-role="card"' in line or "card" in line
