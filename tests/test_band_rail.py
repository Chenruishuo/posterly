"""Tests for the ``band`` measure-role and the vertical-rail (Gate E)
masthead mode.

``band`` is the full-width portrait content band (DESIGN-AXES Axis 1,
portrait translations): like ``banner`` its bottom never feeds the
column-alignment spread, but unlike banner its content IS covered by the
clip / broken-image / letterbox gates (hero-style; the Gate F image-slot
walk-up stays banner-only by design -- see the comment in _POLISH_JS
section 9). Before the role existed, stage/hero bands had to ship as
``banner`` and their content escaped every one of those checks (the
wave-4 "banner blind spot").

Rail mode: every Gate E calibration is written for a HORIZONTAL masthead
strip; a portrait title-spine rail (P5) mis-fired all of them. polish
now detects the rail from the header aspect ratio and swaps the
horizontal calibrations for rail checks, keeping LOGO/BROKEN and the
overflow gate.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import sys
import types

import pytest

from _posterly import measure as _measure
from _posterly import polish as _polish
from _posterly import preflight


# ---- preflight: band nesting --------------------------------------------


def _run_preflight(html: str, tmp_path) -> tuple[int, str, str]:
    p = tmp_path / "p.html"
    p.write_text(html, encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = preflight.cmd_preflight(argparse.Namespace(html=str(p)))
    return rc, out.getvalue(), err.getvalue()


def test_band_under_poster_passes(tmp_path) -> None:
    """A ``band`` directly under ``poster`` (the documented contract for
    portrait stage/hero bands) must preflight clean."""
    html = (
        '<!DOCTYPE html><html><head><title>x</title></head><body>\n'
        '<div data-measure-role="poster">\n'
        '  <header data-measure-role="header"><h1>t</h1></header>\n'
        '  <section data-measure-role="band">stage band</section>\n'
        '  <div data-measure-role="body">\n'
        '    <div data-measure-role="column">\n'
        '      <div data-measure-role="card">c1</div>\n'
        '    </div>\n'
        '  </div>\n'
        '  <section data-measure-role="footer-strip">strip</section>\n'
        '</div>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run_preflight(html, tmp_path)
    assert rc == 0, f"expected PASS for band under poster, got: {err!r}"


def test_band_under_body_fails(tmp_path) -> None:
    """``band`` nested inside ``body`` violates its parent contract
    (bands hang directly off the poster grid) and must be named."""
    html = (
        '<html><body>\n'
        '<div data-measure-role="poster">\n'
        '  <div data-measure-role="body">\n'
        '    <section data-measure-role="band">misplaced</section>\n'
        '    <div data-measure-role="column">\n'
        '      <div data-measure-role="card">c1</div>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run_preflight(html, tmp_path)
    assert rc == 1
    assert "data-measure-role='band'" in err
    assert "inside body" in err


# ---- measure: band in the clip gate, excluded from spread ---------------
# Render-time checks -> need real Chromium (same gating as
# test_clip_integration.py).


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


_HAS_CHROMIUM = _chromium_available()


def _band_poster(band_css: str, band_paragraphs: int) -> str:
    para = ("<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore.</p>")
    band_content = para * band_paragraphs if band_paragraphs else "band"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: flex; flex-direction: column; padding: 60px; }}
  .band {{ height: 400px; background: #eef; {band_css} }}
  .column {{ flex: 1; display: flex; flex-direction: column;
             min-height: 0; }}
  .card {{ flex: 1; border: 2px solid #888; padding: 20px; }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233; }}
  p {{ font-size: 28px; line-height: 1.4; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="band" data-measure-role="band">{band_content}</div>
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">card content</div>
    </div>
    <div class="footer-strip" data-measure-role="footer-strip"></div>
  </div>
</body></html>
"""


def _measure_args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None,
        max_spread=5.0, min_gap=30.0, max_gap=50.0,
        allow_empty_column=False, allow_no_footer_gap=False,
        settle_ms=200, mathjax_timeout_ms=5000,
        min_canvas_fill=0.95, max_canvas_fill=1.01,
        position_tol_px=2.0, max_clip_px=2.0, json_out=None,
    )


def _run_measure(tmp_path, capsys, band_css: str, band_paragraphs: int):
    poster = tmp_path / "poster.html"
    poster.write_text(
        _band_poster(band_css, band_paragraphs), encoding="utf-8")
    rc = _measure.cmd_measure(_measure_args(poster))
    return rc, "".join(capsys.readouterr())


@pytest.mark.skipif(not _HAS_CHROMIUM,
                    reason="playwright + chromium not available")
def test_band_hidden_clip_fires(tmp_path, capsys) -> None:
    # A fixed-height band with overflow:hidden and far too much content
    # clips it silently in print -- exactly the blind spot the role
    # closes. The gate must hard-fail and name the band.
    rc, out = _run_measure(
        tmp_path, capsys, "overflow: hidden;", band_paragraphs=40)
    assert rc == 1
    assert "CLIPPED" in out
    assert "band" in out


@pytest.mark.skipif(not _HAS_CHROMIUM,
                    reason="playwright + chromium not available")
def test_band_content_fits_no_false_positive(tmp_path, capsys) -> None:
    # Same overflow:hidden band with content that fits: silent, and the
    # poster PASSes -- which also pins the role's other half: the band's
    # own bottom (mid-poster, far above the column bottom) must NOT
    # enter the alignment spread.
    rc, out = _run_measure(
        tmp_path, capsys, "overflow: hidden;", band_paragraphs=0)
    assert rc == 0, out
    assert "PASS" in out
    assert "CLIPPED" not in out


# ---- polish: band figures + rail-mode Gate E (mocked playwright) --------


def _install_fake_playwright(monkeypatch):
    class _PW:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    mod = types.ModuleType("playwright.sync_api")
    mod.TimeoutError = type("_T", (Exception,), {})
    mod.sync_playwright = lambda: _PW()
    parent = types.ModuleType("playwright")
    parent.sync_api = mod
    monkeypatch.setitem(sys.modules, "playwright", parent)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", mod)


class _Page:
    def __init__(self, data):
        self._data = data

    def goto(self, *a, **k):
        pass

    def evaluate(self, *a, **k):
        return self._data


class _Browser:
    def close(self):
        pass


def _poster_html(tmp_path):
    p = tmp_path / "poster.html"
    p.write_text(
        "<html><head><style>@page { size: 24in 36in }</style></head>"
        "<body><div data-measure-role=\"poster\">"
        "<div data-measure-role=\"column\">"
        "<div data-measure-role=\"card\"></div></div></div></body></html>",
        encoding="utf-8",
    )
    return p


def _polish_args(html, **over):
    base = dict(
        html=str(html), canvas=None, settle_ms=500,
        mathjax_timeout_ms=15000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, tall_min_ratio=0.36, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10,
        logo_max_width_ratio=0.22, logo_qr_tol=0.15,
        rightblock_max_ratio=0.32, title_min_ratio=0.45, strict=False,
    )
    base.update(over)
    return argparse.Namespace(**base)


def _run_polish(monkeypatch, tmp_path, capsys, data, **args_over):
    _install_fake_playwright(monkeypatch)
    page = _Page(data)
    monkeypatch.setattr(
        _polish._render, "open_print_emulated_page",
        lambda p, vp: (_Browser(), None, page),
    )
    monkeypatch.setattr(
        _polish._render, "settle_page", lambda *a, **k: object())
    monkeypatch.setattr(
        _polish._render, "hard_fail_on_settle_problems",
        lambda *a, **k: None,
    )
    rc = _polish.cmd_polish(_polish_args(_poster_html(tmp_path),
                                         **args_over))
    return "".join(capsys.readouterr()), rc


def test_band_broken_image_fires(tmp_path, monkeypatch, capsys) -> None:
    """A zero-natural-size raster in a band surfaces FIG/BROKEN -- the
    check that used to skip banner-role content entirely."""
    data = {
        "figures": [
            {"src": "images/gone.png", "role": "band",
             "rendered_w": 800.0, "rendered_h": 300.0, "card_w": 2000.0,
             "natural_w": 0.0, "natural_h": 0.0},
        ],
    }
    out, rc = _run_polish(monkeypatch, tmp_path, capsys, data)
    assert "FIG/BROKEN" in out
    assert rc == 0


def test_band_stage_letterbox_fires_with_band_label(
    tmp_path, monkeypatch, capsys
) -> None:
    """A narrow-AR picture height-constrained in a wide-short band stage
    leaves symmetric side voids -> BAND/STAGE-LETTERBOX (same geometry
    as the hero branch, band-labelled)."""
    data = {
        "figures": [
            # AR 1.25 picture in a 5:1 stage, object-fit contain:
            # content_w = 400*1.25 = 500 of 2000 -> fill 25% < 55%,
            # ar_mult 4.0 > 1.6, voids symmetric.
            {"src": "images/lock.svg", "role": "band",
             "rendered_w": 2000.0, "rendered_h": 400.0, "card_w": 2200.0,
             "stage_w": 2000.0, "stage_h": 400.0,
             "off_left": 0.0, "off_right": 0.0,
             "natural_w": 500.0, "natural_h": 400.0,
             "obj_fit": "contain"},
        ],
    }
    out, rc = _run_polish(monkeypatch, tmp_path, capsys, data)
    assert "BAND/STAGE-LETTERBOX" in out
    assert rc == 0


def test_hero_letterbox_label_unchanged(
    tmp_path, monkeypatch, capsys
) -> None:
    """Same geometry under role=hero keeps the HERO label."""
    data = {
        "figures": [
            {"src": "images/pano.png", "role": "hero",
             "rendered_w": 2000.0, "rendered_h": 400.0, "card_w": 2200.0,
             "stage_w": 2000.0, "stage_h": 400.0,
             "off_left": 0.0, "off_right": 0.0,
             "natural_w": 500.0, "natural_h": 400.0,
             "obj_fit": "contain"},
        ],
    }
    out, _rc = _run_polish(monkeypatch, tmp_path, capsys, data)
    assert "HERO/STAGE-LETTERBOX" in out
    assert "BAND/STAGE-LETTERBOX" not in out


# ---- polish: rail-mode Gate E -------------------------------------------

# A P5-style rail: 360px wide, 3200px tall (aspect ~8.9, far past the
# 1.5 threshold), content box inset 20px on every edge.
_RAIL_HEADER = dict(
    header_w=360.0, header_h=3200.0, header_cx=180.0,
    header_content_left=20.0, header_content_right=340.0,
    header_content_top=20.0, header_content_bottom=3180.0,
)


def test_rail_skips_horizontal_calibrations(
    tmp_path, monkeypatch, capsys
) -> None:
    """In rail mode the strip calibrations must stay silent: a logo at
    50% of rail width (would be LOGO/WIDE on a strip), a logo/QR height
    mismatch (no height-matched row exists in a stack), and a 69%-wide
    block (would be TITLE-SQUEEZED). The summary names the mode."""
    data = dict(
        _RAIL_HEADER,
        logos=[{"src": "logo.png", "rendered_w": 180.0,
                "rendered_h": 120.0, "natural_w": 400.0,
                "natural_h": 300.0, "slot_classes": "logo-slot",
                "venue": False, "stacked": False}],
        qrs=[{"rendered_h": 200.0}],
        headerBlocks=[
            {"cls": "right-block", "kind": "right", "w": 250.0,
             "cx": 180.0, "left": 30.0, "right": 280.0,
             "top": 100.0, "bottom": 400.0},
            {"cls": "title-block", "kind": "title", "w": 300.0,
             "cx": 180.0, "left": 30.0, "right": 330.0,
             "top": 500.0, "bottom": 2000.0},
        ],
    )
    out, rc = _run_polish(monkeypatch, tmp_path, capsys, data)
    # The rail-mode summary line itself names the skipped calibrations,
    # so assert on the WARN prefix, not the bare codes.
    assert "WARN: LOGO/WIDE" not in out
    assert "WARN: LOGO/QR-MISMATCH" not in out
    assert "TITLE-SQUEEZED" not in out
    assert "TITLE-OFFCENTER" not in out
    assert "HEADER/OVERFLOW" not in out
    assert "vertical rail" in out
    assert rc == 0


def test_rail_logo_wider_than_rail_fires(
    tmp_path, monkeypatch, capsys
) -> None:
    data = dict(
        _RAIL_HEADER,
        logos=[{"src": "logo.png", "rendered_w": 350.0,
                "rendered_h": 200.0, "natural_w": 700.0,
                "natural_h": 400.0, "slot_classes": "logo-slot",
                "venue": False, "stacked": False}],
    )
    out, _rc = _run_polish(monkeypatch, tmp_path, capsys, data)
    assert "LOGO/WIDE" in out
    assert "spills past the rail" in out


def test_rail_broken_logo_still_fires(
    tmp_path, monkeypatch, capsys
) -> None:
    """LOGO/BROKEN is unconditional -- rail mode must never mute it."""
    data = dict(
        _RAIL_HEADER,
        logos=[{"src": "gone.png", "rendered_w": 100.0,
                "rendered_h": 100.0, "natural_w": 0.0, "natural_h": 0.0,
                "slot_classes": "logo-slot", "venue": False,
                "stacked": False}],
    )
    out, _rc = _run_polish(monkeypatch, tmp_path, capsys, data)
    assert "LOGO/BROKEN" in out


def test_rail_vertical_overflow_fires(
    tmp_path, monkeypatch, capsys
) -> None:
    """A stacked block spilling past the rail's bottom content edge is
    the rail's overflow axis; the strip gate never looked at it."""
    data = dict(
        _RAIL_HEADER,
        headerBlocks=[
            {"cls": "right-stack", "kind": "right", "w": 250.0,
             "cx": 180.0, "left": 30.0, "right": 280.0,
             "top": 2900.0, "bottom": 3300.0},
        ],
    )
    out, _rc = _run_polish(monkeypatch, tmp_path, capsys, data)
    assert "HEADER/OVERFLOW" in out
    assert "top/bottom" in out


def test_horizontal_header_behavior_unchanged(
    tmp_path, monkeypatch, capsys
) -> None:
    """Control: a normal strip masthead keeps every horizontal
    calibration -- the same 30%-of-width logo + QR mismatch that rail
    mode ignores must still fire here."""
    data = dict(
        header_w=2000.0, header_h=150.0, header_cx=1000.0,
        header_content_left=20.0, header_content_right=1980.0,
        header_content_top=10.0, header_content_bottom=140.0,
        logos=[{"src": "logo.png", "rendered_w": 600.0,
                "rendered_h": 60.0, "natural_w": 1200.0,
                "natural_h": 120.0, "slot_classes": "logo-slot",
                "venue": False, "stacked": False}],
        qrs=[{"rendered_h": 100.0}],
    )
    out, _rc = _run_polish(monkeypatch, tmp_path, capsys, data)
    assert "LOGO/WIDE" in out
    assert "% of header width" in out
    assert "LOGO/QR-MISMATCH" in out
    assert "vertical rail" not in out


# ---- polish: end-to-end through the real _POLISH_JS ---------------------
# The mocked tests above pin the Python side only; this one renders a
# real rail+band poster so the NEW collection paths execute in Chromium:
# the band img must land in `figures` (FIG/BROKEN) and NOT in
# `bannerImgs` (Gate F stays banner-only), header_h + the four content
# edges must ship (rail detection + vertical overflow).

_E2E_POSTER = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; background: #fff; }
  .poster { width: 24in; height: 36in; background: #fff; color: #111;
            display: grid; grid-template-columns: 360px 1fr;
            grid-template-rows: 600px 1fr; }
  .rail   { grid-row: 1 / 3; grid-column: 1; padding: 20px;
            background: #eee; }
  .right-block { width: 200px; height: 4000px; background: #ddd; }
  .band   { grid-row: 1; grid-column: 2; padding: 20px; }
  .column { grid-row: 2; grid-column: 2; display: flex;
            flex-direction: column; }
  .card   { flex: 1; border: 2px solid #888; padding: 20px; }
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <header class="rail" data-measure-role="header">
      <div class="right-block">stacked block</div>
    </header>
    <div class="band" data-measure-role="band">
      <!-- display:block matters: a broken INLINE img with alt collapses
           to Chromium's 24x18 icon (CSS size ignored) and would duck the
           50px collection floor; the shipped figure components set
           display:block, under which the CSS size applies. -->
      <img src="missing.png" alt="x"
           style="display:block;width:300px;height:200px">
    </div>
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">card content</div>
    </div>
  </div>
</body></html>
"""


@pytest.mark.skipif(not _HAS_CHROMIUM,
                    reason="playwright + chromium not available")
def test_rail_band_end_to_end(tmp_path, capsys) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_E2E_POSTER, encoding="utf-8")
    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())
    # Rail detected from the real header box (360 wide x full height).
    assert "vertical rail" in out
    # Band img collected by the band selector -> FIG/BROKEN fires.
    assert "figures checked     : 1" in out
    assert "WARN: FIG/BROKEN" in out
    # ...and NOT by the Gate F banner walk-up.
    assert "banner images       : 0" in out
    # The 4000px block spills the rail's bottom content edge.
    assert "WARN: HEADER/OVERFLOW" in out
    assert "top/bottom" in out
    assert rc == 0
