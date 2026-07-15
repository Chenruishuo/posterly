"""Chromium-gated integration tests for ``poster_check.py pack`` --
the advisory column-feasibility pre-check. Verifies the browser
endpoint-probe end to end: a column that cannot fit even with its
figure at the Gate A floor reads REPACK_RECOMMENDED; a comfortable
column reads OK; original styles are restored (the probe must not
leave inline overrides behind in the report snapshot).

Skipped when Playwright / Chromium isn't installed.
"""
from __future__ import annotations

import argparse
import json

import pytest

from _posterly import pack as _pack


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


# 24x36in canvas -> 2304x3456px viewport. Column capacity ~3050px to
# the footer-strip. `filler_px` fixes the text block height; the figure
# is a wide (AR=2) SVG sized at 100% card width by default.
def _poster(filler_px: int) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: flex; flex-direction: column; padding: 60px; }}
  .column {{ flex: 1; display: flex; flex-direction: column;
             gap: 24px; }}
  /* flex-shrink: 0 -- without it an over-full column COMPRESSES the
     fixed-height cards back into the track and every probe reads the
     same bottom, hiding exactly the overflow pack must detect. */
  .card {{ border: 2px solid #888; padding: 20px; flex-shrink: 0; }}
  .filler {{ height: {filler_px}px; background: #f4f4f4; }}
  .card img {{ width: 100%; height: auto; display: block; }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233; }}
  p {{ font-size: 28px; line-height: 1.4; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">
        <p>Text card.</p><div class="filler"></div>
      </div>
      <div class="card" data-measure-role="card">
        <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='400'%3E%3Crect width='800' height='400' fill='%23cbd5e1'/%3E%3C/svg%3E"
             alt="wide figure">
      </div>
    </div>
    <div class="footer-strip" data-measure-role="footer-strip"></div>
  </div>
</body></html>
"""


def _args(html, json_out=None, strict=False) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, max_spread=5.0,
        min_gap=30.0, max_gap=50.0,
        wide_min_ratio=0.65, square_min_ratio=0.55, tall_min_ratio=0.36,
        settle_ms=200, mathjax_timeout_ms=5000,
        strict=strict, json_out=json_out,
    )


def _run(tmp_path, capsys, filler_px, **kw):
    poster = tmp_path / "poster.html"
    poster.write_text(_poster(filler_px), encoding="utf-8")
    report = tmp_path / "pack.json"
    rc = _pack.cmd_pack(_args(poster, json_out=str(report), **kw))
    out = "".join(capsys.readouterr())
    data = json.loads(report.read_text()) if report.exists() else None
    return rc, out, data


def test_overfull_column_is_repack_recommended(tmp_path, capsys) -> None:
    # Card1 figure at FLOOR (0.65 * ~2160 card = ~1404w -> ~702h) plus
    # a 2600px filler overflows the canvas: the flex column pushes the
    # footer-strip off-page, which pack must flag as CANVAS OVERFLOW
    # (anchoring the window on the pushed strip would legitimize it).
    rc, out, data = _run(tmp_path, capsys, filler_px=2600)
    assert rc == 0  # advisory by default
    assert "CANVAS OVERFLOW" in out
    assert data["canvas_overflow"] is True
    assert "REPACK_RECOMMENDED" in out
    assert data["columns"][0]["verdict"] == "REPACK_RECOMMENDED"
    # A global overflow must never read as an all-clear.
    assert "[pack] OK" not in out


def test_comfortable_column_is_ok(tmp_path, capsys) -> None:
    # filler 2000 -> column bottom spans ~2921 (figure at floor ~710h)
    # .. ~3303 (ceiling ~1092h), straddling the 3186..3206 window -> OK.
    rc, out, data = _run(tmp_path, capsys, filler_px=2000)
    assert rc == 0
    assert data["columns"][0]["verdict"] == "OK"
    assert "REPACK_RECOMMENDED" not in out


def test_underfull_column_flagged(tmp_path, capsys) -> None:
    # Tiny filler: even the figure at its ceiling leaves the column
    # far short of the window.
    rc, out, data = _run(tmp_path, capsys, filler_px=200)
    assert rc == 0
    assert data["columns"][0]["verdict"] == "FIGURE_ONLY_UNDERFILL"


def test_strict_exit_on_infeasible(tmp_path, capsys) -> None:
    rc, _out, _data = _run(tmp_path, capsys, filler_px=2600, strict=True)
    assert rc == 1


def test_probe_restores_styles(tmp_path, capsys) -> None:
    """After a pack run, re-running pack yields the same base geometry
    (no leftover inline width overrides) -- proxied by verdict
    stability across two runs on the same file."""
    rc1, _o1, d1 = _run(tmp_path, capsys, filler_px=2000)
    rc2, _o2, d2 = _run(tmp_path, capsys, filler_px=2000)
    assert (rc1, d1["columns"][0]["verdict"]) == (
        rc2, d2["columns"][0]["verdict"])
    assert d1["columns"][0]["probed_envelope"] == pytest.approx(
        d2["columns"][0]["probed_envelope"], abs=2.0)


# Two text-only columns (point envelopes: no figures to probe) whose
# bottoms sit 3152 / 3168 px -- both inside the [3150, 3170] window
# anchored on the strip at 3200, but 16 px apart: individually OK, yet
# no figure sizing can ever bring them within --max-spread 5. Without
# a hero this is exactly the cross-column bound's territory; the hero
# variant keeps the strip at the same 3200 by trading 300px of row
# height for the hero panel.
def _two_col_poster(with_hero: bool) -> str:
    row_h = 2800 if with_hero else 3100
    hero = (
        '<div data-measure-role="hero" '
        'style="height:300px; background:#345;"></div>'
        if with_hero else ""
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: flex; flex-direction: column; padding: 60px; }}
  .row {{ display: flex; gap: 40px; height: {row_h}px; }}
  .column {{ flex: 1; display: flex; flex-direction: column; }}
  .card {{ border: 2px solid #888; padding: 20px; flex-shrink: 0; }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233;
                   flex-shrink: 0; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="row">
      <div class="column" data-measure-role="column">
        <div class="card" data-measure-role="card">
          <div style="height:3048px"></div>
        </div>
      </div>
      <div class="column" data-measure-role="column">
        <div class="card" data-measure-role="card">
          <div style="height:3064px"></div>
        </div>
      </div>
    </div>
    {hero}
    <div class="footer-strip" data-measure-role="footer-strip"></div>
  </div>
</body></html>
"""


def test_cross_column_bound_fires_without_hero(tmp_path, capsys) -> None:
    """Baseline for the hero test below: every column verdict is OK,
    so --strict can only be failing on the cross-column bound."""
    poster = tmp_path / "poster.html"
    poster.write_text(_two_col_poster(False), encoding="utf-8")
    report = tmp_path / "pack.json"
    rc = _pack.cmd_pack(_args(poster, json_out=str(report), strict=True))
    out = "".join(capsys.readouterr())
    data = json.loads(report.read_text())
    assert all(c["verdict"] == "OK" for c in data["columns"])
    assert data["cross_column_min_spread"] is not None
    assert data["cross_column_min_spread"] >= 5.0
    assert "CROSS-COLUMN" in out
    assert rc == 1


def test_hero_suppresses_cross_check_consistently(
    tmp_path, capsys
) -> None:
    """REGRESSION: same two columns whose cross bound FIRES in the
    baseline test -- adding a hero must withhold that bound EVERYWHERE
    (stdout note, JSON null) and --strict must no longer be tripped by
    a hidden cross value."""
    poster = tmp_path / "poster.html"
    poster.write_text(_two_col_poster(True), encoding="utf-8")
    report = tmp_path / "pack.json"
    rc = _pack.cmd_pack(_args(poster, json_out=str(report), strict=True))
    out = "".join(capsys.readouterr())
    data = json.loads(report.read_text())
    assert all(c["verdict"] == "OK" for c in data["columns"])
    assert "UNSUPPORTED_HERO" in out
    assert "CROSS-COLUMN" not in out
    assert data["hero_present"] is True
    assert data["cross_column_min_spread"] is None
    assert rc == 0


# Anchor strip IN canvas (bottom 3214 < 3456), but the footer under it
# ends at 3514 -- off canvas. The column is NOT blamable: its bottom
# 2954 + min-gap 30 + the 460px strip/footer block fits 3456. So a
# check that looks only at the strip bottom sees nothing wrong at all.
_FOOTER_OVERFLOW_POSTER = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; background: #fff; }
  .poster { width: 24in; height: 36in; background: #fff;
            display: flex; flex-direction: column; padding: 60px; }
  .column { flex: 1; display: flex; flex-direction: column; }
  .card { border: 2px solid #888; padding: 20px; flex-shrink: 0; }
  .footer-strip { height: 160px; margin-top: 100px; background: #233;
                  flex-shrink: 0; }
  .footer { height: 300px; background: #455; flex-shrink: 0; }
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">
        <div style="height:2850px"></div>
      </div>
    </div>
    <div class="footer-strip" data-measure-role="footer-strip"></div>
    <div class="footer" data-measure-role="footer"></div>
  </div>
</body></html>
"""


def test_footer_pushed_off_canvas_is_canvas_overflow(
    tmp_path, capsys
) -> None:
    """REGRESSION: the overflow check must cover the WHOLE downstream
    block, not just the anchor strip -- here the strip stays in canvas
    while the footer below it is pushed off, and no single column is
    blamable, so --strict can only be failing on canvas_overflow."""
    poster = tmp_path / "poster.html"
    poster.write_text(_FOOTER_OVERFLOW_POSTER, encoding="utf-8")
    report = tmp_path / "pack.json"
    rc = _pack.cmd_pack(_args(poster, json_out=str(report), strict=True))
    out = "".join(capsys.readouterr())
    data = json.loads(report.read_text())
    assert "CANVAS OVERFLOW" in out
    assert data["canvas_overflow"] is True
    assert "[pack] OK" not in out
    assert all(c["verdict"] == "OK" for c in data["columns"])
    assert "no single column accounts" in out
    assert rc == 1
