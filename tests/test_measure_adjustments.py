"""Unit tests for ``compute_adjustment_hints`` -- the per-column
adjustment hints surfaced when ``measure`` fails its gap/spread gate.

The hint computation is a pure function (no Playwright, no DOM): given
each column's last-card-bottom and the footer-strip top, it yields the
**shared passing band** plus a "keep / grow / trim" hint per column.
Testing it as a pure function pins the contract without booting a
browser.

Contract (rev 2, after the paper2poster-inspired rework):

- The band is centred on ``strip_top - (min_gap + max_gap)/2`` with
  width ``max_spread - epsilon``, intersected with the gap window --
  columns that ALL land inside one band pass BOTH gates (gap by the
  window intersection, spread strictly because the band is narrower
  than ``max_spread``).
- "keep" means inside-the-band, NOT ``|delta| <= max_spread``: the old
  rule let two columns sit at opposite edges of a +/-max_spread
  tolerance, both reading "keep" while their pairwise spread was 2x the
  gate (regression pinned below).
- Safe ranges are integer-rounded INWARD so a hint can never point
  outside the true band.
"""
from __future__ import annotations

from _posterly.measure import compute_adjustment_hints, format_band


def _hints(adjustments: list[tuple[str, float, str]]) -> dict[str, str]:
    """Pull just the hint string keyed by column name."""
    return {name: hint for name, _b, hint in adjustments}


def test_band_is_centred_and_narrower_than_max_spread() -> None:
    """Band centre = strip_top - (min_gap+max_gap)/2; width
    = max_spread - epsilon, so worst-case in-band spread stays
    strictly under the gate."""
    (lo, hi), _ = compute_adjustment_hints(
        bottoms=[("col0", 3000.0)],
        strip_top=3120.0,
        min_gap=30.0,
        max_gap=50.0,
        max_spread=5.0,
    )
    center = (lo + hi) / 2
    assert center == 3080.0
    assert (hi - lo) == 4.5  # 5.0 - default epsilon 0.5
    assert hi - lo < 5.0


def test_band_clamped_to_gap_window() -> None:
    """A huge --max-spread cannot widen the band past the footer-gap
    window [strip_top - max_gap, strip_top - min_gap]."""
    (lo, hi), _ = compute_adjustment_hints(
        bottoms=[("col0", 3000.0)],
        strip_top=3120.0,
        min_gap=30.0,
        max_gap=50.0,
        max_spread=100.0,
    )
    assert lo >= 3120.0 - 50.0
    assert hi <= 3120.0 - 30.0


def test_double_keep_spread_regression() -> None:
    """REGRESSION (pre-rework bug): two columns at target +/-5 px with
    max_spread=5 both read 'keep' under the old |delta|<=tol rule, yet
    their pairwise spread was 10 px -- the gate still failed while the
    hints said nothing needed touching. In-band semantics fix this:
    at most one of them can be inside a band narrower than 5 px."""
    _, adj = compute_adjustment_hints(
        bottoms=[("col0", 3075.0), ("col1", 3085.0)],  # centre 3080 +/-5
        strip_top=3120.0,
        min_gap=30.0,
        max_gap=50.0,
        max_spread=5.0,
    )
    h = _hints(adj)
    keeps = [k for k, v in h.items() if v == "keep"]
    assert len(keeps) == 0  # both sit OUTSIDE the 4.5px band
    assert h["col0"].startswith("grow ")
    assert h["col1"].startswith("trim ")


def test_keep_inside_band_only() -> None:
    """A bottom inside the band -> keep; just outside -> a directed
    hint."""
    (lo, hi), adj = compute_adjustment_hints(
        bottoms=[
            ("col0", 3080.0),   # dead centre -> keep
            ("col1", 3081.5),   # inside (band half-width 2.25) -> keep
            ("col2", 3083.0),   # outside hi=3082.25 -> trim
            ("col3", 3050.0),   # far short -> grow
        ],
        strip_top=3120.0,
        min_gap=30.0,
        max_gap=50.0,
        max_spread=5.0,
    )
    assert lo <= 3080.0 <= hi and lo <= 3081.5 <= hi
    h = _hints(adj)
    assert h["col0"] == "keep"
    assert h["col1"] == "keep"
    assert h["col2"].startswith("trim ~3 px")
    assert h["col3"].startswith("grow ~30 px")


def test_safe_range_rounds_inward_and_stays_in_band() -> None:
    """The integer safe range never points outside the real band: its
    endpoints, applied to the column bottom, land within [lo, hi]."""
    (lo, hi), adj = compute_adjustment_hints(
        bottoms=[("col0", 3050.3)],
        strip_top=3120.0,
        min_gap=30.0,
        max_gap=50.0,
        max_spread=5.0,
    )
    hint = _hints(adj)["col0"]
    # hint shape: "grow ~30 px [safe +28..+32]"
    rng = hint.split("[safe ")[1].rstrip("]")
    d_lo, d_hi = (int(x) for x in rng.split(".."))
    assert d_lo <= d_hi
    assert lo <= 3050.3 + d_lo <= hi
    assert lo <= 3050.3 + d_hi <= hi


def test_preserves_input_order_and_names() -> None:
    """Hints come back in the same order the caller supplied. Hero rows
    keep their hero name -- the cmd_measure caller mixes 'col0', 'col1',
    'hero' in one list and the print loop relies on stable order."""
    _, adj = compute_adjustment_hints(
        bottoms=[("col1", 3000.0), ("hero", 3060.0), ("col0", 3120.0)],
        strip_top=3120.0,
        min_gap=30.0,
        max_gap=50.0,
        max_spread=5.0,
    )
    assert [name for name, _b, _h in adj] == ["col1", "hero", "col0"]


def test_no_whole_pixel_delta_is_not_called_safe() -> None:
    """When no INTEGER delta lands inside a sub-pixel band, the hint
    must not claim a '[safe ...]' range -- it gives the exact
    fractional target instead (regression: the old fallback labelled
    round(delta) as safe even when it landed outside the band)."""
    (lo, hi), adj = compute_adjustment_hints(
        bottoms=[("col0", 3079.51)],
        strip_top=3120.0,
        min_gap=39.9,       # window [3079.9, 3080.1]
        max_gap=40.1,
        max_spread=5.0,     # band clamped to the 0.2px window
    )
    assert hi - lo < 1.0
    hint = _hints(adj)["col0"]
    assert "[safe" not in hint
    assert "no whole-px safe delta" in hint
    # The aimed fractional delta must land the bottom STRICTLY inside
    # the band -- the display carries two decimals and aims at the
    # band centre, so no rounding tolerance is owed here.
    aimed = float(hint.split("aim ")[1].split(" px")[0])
    assert lo <= 3079.51 + aimed <= hi


def test_zero_width_band_gets_enough_decimals() -> None:
    """A LEGAL --max-spread 0.5 collapses the band to a point (width
    = max_spread - epsilon = 0), where two display decimals can miss
    the target. Contract: applying the DISPLAYED delta lands within
    1e-6 px of the point target."""
    (lo, hi), adj = compute_adjustment_hints(
        bottoms=[("col0", 3079.996)],
        strip_top=3120.0,
        min_gap=30.0,
        max_gap=50.0,
        max_spread=0.5,
    )
    assert hi == lo
    hint = _hints(adj)["col0"]
    assert "no whole-px safe delta" in hint
    aimed = float(hint.split("aim ")[1].split(" px")[0])
    assert abs((3079.996 + aimed) - lo) < 1e-6


def test_band_display_rounds_inward() -> None:
    """The printed band is never WIDER than the true one: off-grid
    edges round toward the inside (a --max-spread 4.998 band
    3077.751..3082.249 must not display as 3077.75..3082.25)."""
    assert format_band(3077.751, 3082.249) == "3077.76..3082.24"
    # On-grid edges are untouched -- including ones whose scaled
    # product lands a few ULP off its integer (2500.01 * 100 =
    # 250001.00000000003 must not get ceil'd a whole step inward).
    assert format_band(3077.75, 3082.25) == "3077.75..3082.25"
    assert format_band(2500.01, 2500.10) == "2500.01..2500.10"
    # A point band collapses to its centre instead of inverting.
    assert format_band(3080.0, 3080.0) == "3080.000000..3080.000000"


def test_degenerate_flags_fall_back_to_centre() -> None:
    """min_gap > max_gap (user error) empties the window; the function
    degrades to a point target instead of crashing or inverting."""
    (lo, hi), adj = compute_adjustment_hints(
        bottoms=[("col0", 3000.0)],
        strip_top=3120.0,
        min_gap=50.0,
        max_gap=30.0,
        max_spread=5.0,
    )
    assert lo == hi
    assert _hints(adj)["col0"].startswith("grow ")


def test_handles_off_canvas_strip_top() -> None:
    """If the footer-strip itself rendered past the canvas (a real
    failure mode caught by the structure gate), the hints still compute
    -- the caller is the right place to decide whether to print them."""
    (lo, hi), adj = compute_adjustment_hints(
        bottoms=[("col0", 3000.0), ("col1", 3050.0)],
        strip_top=3500.0,  # off-canvas
        min_gap=30.0,
        max_gap=50.0,
        max_spread=5.0,
    )
    assert (lo + hi) / 2 == 3460.0
    h = _hints(adj)
    # Both columns are far below the (impossible) target -> grow.
    assert h["col0"].startswith("grow ")
    assert h["col1"].startswith("grow ")
