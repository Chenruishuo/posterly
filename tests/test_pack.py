"""Unit tests for ``_posterly.pack``'s pure logic -- verdict
classification (``pack_verdicts``), AR-band selection (``band_for_ar``)
and endpoint planning (``plan_endpoints``). The browser probing itself
is covered by the Chromium-gated integration test.
"""
from __future__ import annotations

from _posterly.pack import band_for_ar, pack_verdicts, plan_endpoints


ALLOWED = (3070.0, 3090.0)  # strip 3120, gaps [30, 50]


def _verdict(results: list[dict], name: str) -> str:
    return next(r["verdict"] for r in results if r["name"] == name)


def test_ok_when_window_reachable() -> None:
    results, cross = pack_verdicts(
        [("col0", 3000.0, 3150.0)], ALLOWED, 5.0
    )
    assert _verdict(results, "col0") == "OK"
    assert cross is None


def test_center_offset_still_ok() -> None:
    """REGRESSION vs the naive centre-distance design: a column whose
    reachable range covers only the EDGE of the window (never its
    centre) is still feasible -- interval intersection, not distance
    to centre."""
    results, _ = pack_verdicts(
        [("col0", 3085.0, 3200.0)], ALLOWED, 5.0
    )
    assert _verdict(results, "col0") == "OK"


def test_overfull_and_underfull() -> None:
    results, _ = pack_verdicts(
        [
            ("col0", 3095.0, 3200.0),  # floor bottom already past window
            ("col1", 2900.0, 3060.0),  # ceiling still short of window
        ],
        ALLOWED, 5.0,
    )
    assert _verdict(results, "col0") == "REPACK_RECOMMENDED"
    assert _verdict(results, "col1") == "FIGURE_ONLY_UNDERFILL"


def test_boundary_touching_is_ok() -> None:
    """Reachable range touching the window edge exactly -> feasible."""
    results, _ = pack_verdicts(
        [("col0", 3090.0, 3200.0), ("col1", 2900.0, 3070.0)],
        ALLOWED, 5.0,
    )
    assert _verdict(results, "col0") == "OK"
    assert _verdict(results, "col1") == "OK"


def test_swapped_reachable_bounds_tolerated() -> None:
    """Text reflow can make the 'lo' probe land BELOW the 'hi' probe;
    the verdict logic must normalise instead of misclassifying."""
    results, _ = pack_verdicts(
        [("col0", 3150.0, 3000.0)], ALLOWED, 5.0
    )
    assert _verdict(results, "col0") == "OK"


def test_cross_column_bound_fires() -> None:
    """Two individually-OK columns whose clamped windows sit further
    apart than max_spread can never meet: col0 reaches only the very
    top of the window, col1 only the very bottom."""
    allowed = (3000.0, 3100.0)  # widened window to make room
    results, cross = pack_verdicts(
        [
            ("col0", 2900.0, 3005.0),  # clamp -> [3000, 3005]
            ("col1", 3080.0, 3200.0),  # clamp -> [3080, 3100]
        ],
        allowed, 5.0,
    )
    assert all(r["verdict"] == "OK" for r in results)
    assert cross is not None and cross >= 5.0


def test_cross_column_bound_quiet_when_meetable() -> None:
    results, cross = pack_verdicts(
        [("col0", 3000.0, 3150.0), ("col1", 3010.0, 3160.0)],
        ALLOWED, 5.0,
    )
    assert cross is None


def test_band_for_ar_classes() -> None:
    assert band_for_ar(2.0) == (0.65, 1.00)   # wide
    assert band_for_ar(1.0) == (0.55, 0.75)   # square
    assert band_for_ar(0.5) == (0.36, 0.60)   # tall
    # Class boundaries mirror polish: >1.3 wide, >=0.8 square.
    assert band_for_ar(1.3) == (0.55, 0.75)
    assert band_for_ar(0.8) == (0.55, 0.75)


def test_plan_endpoints_skips_and_plans() -> None:
    meta = [
        # Normal wide raster figure on a 1000px card.
        {"i": 0, "src": "a.png", "fig_layout": "",
         "rendered_w": 600.0, "rendered_h": 300.0, "card_w": 1000.0,
         "natural_w": 1200, "natural_h": 600},
        # beside-text opt-out: untouched.
        {"i": 1, "src": "b.png", "fig_layout": "beside-text",
         "rendered_w": 500.0, "rendered_h": 700.0, "card_w": 1000.0,
         "natural_w": 500, "natural_h": 700},
        # Inline icon: untouched.
        {"i": 2, "src": "icon.svg", "fig_layout": "",
         "rendered_w": 30.0, "rendered_h": 30.0, "card_w": 1000.0,
         "natural_w": 0, "natural_h": 0},
        # SVG (zero natural size): AR from the rendered box.
        {"i": 3, "src": "d.svg", "fig_layout": "",
         "rendered_w": 400.0, "rendered_h": 800.0, "card_w": 1000.0,
         "natural_w": 0, "natural_h": 0},
        # Broken: zero natural AND zero rendered.
        {"i": 4, "src": "gone.png", "fig_layout": "",
         "rendered_w": 100.0, "rendered_h": 0.0, "card_w": 1000.0,
         "natural_w": 0, "natural_h": 0},
        # Broken RASTER with CSS-forced box: zero natural size but a
        # non-zero rendered box. Must NOT take the SVG rendered-AR
        # path -- probing it would size a blank rectangle.
        {"i": 5, "src": "dead.png", "fig_layout": "",
         "rendered_w": 400.0, "rendered_h": 300.0, "card_w": 1000.0,
         "natural_w": 0, "natural_h": 0},
        # Broken raster at the browser's default 16x16 placeholder
        # box: must be diagnosed as broken, NOT "inline icon" (the
        # icon check would otherwise catch it first).
        {"i": 6, "src": "tiny-broken.png", "fig_layout": "",
         "rendered_w": 16.0, "rendered_h": 16.0, "card_w": 1000.0,
         "natural_w": 0, "natural_h": 0},
        # Recognised SVG that rendered NOTHING: broken too, and again
        # not "inline icon" (0 < 50 would catch it first).
        {"i": 7, "src": "empty.svg", "fig_layout": "",
         "rendered_w": 0.0, "rendered_h": 0.0, "card_w": 1000.0,
         "natural_w": 0, "natural_h": 0},
    ]
    lo, hi, skipped = plan_endpoints(
        meta, wide_min=0.65, square_min=0.55, tall_min=0.36
    )
    planned = {int(i) for i, _w in lo}
    assert planned == {0, 3}
    assert dict(lo)[0] == 650.0 and dict(hi)[0] == 1000.0   # wide band
    assert dict(lo)[3] == 360.0 and dict(hi)[3] == 600.0    # tall band
    reasons = {s["src"]: s["reason"] for s in skipped}
    assert "b.png" in reasons and "beside-text" in reasons["b.png"]
    assert "icon" in reasons["icon.svg"]
    assert "broken" not in reasons["icon.svg"]
    assert "gone.png" in reasons and "broken" in reasons["gone.png"]
    assert "dead.png" in reasons and "broken" in reasons["dead.png"]
    assert "broken" in reasons["tiny-broken.png"]
    assert "icon" not in reasons["tiny-broken.png"]
    assert "broken" in reasons["empty.svg"]
    assert "icon" not in reasons["empty.svg"]
