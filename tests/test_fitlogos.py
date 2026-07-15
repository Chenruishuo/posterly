"""Unit tests for ``_posterly.fitlogos`` pure geometry -- the row
partition search (``best_arrangement``), its uniform-height contract,
and the snippet renderer. The browser probe is exercised manually (the
subcommand is a read-only advisor; nothing to pin beyond the math).
"""
from __future__ import annotations

import pytest

from _posterly.fitlogos import (
    DEFAULT_HGAP_PX,
    ROW_GAP_FRAC,
    Mark,
    best_arrangement,
    render_snippet,
)


def _m(ar: float, opaque: float = 1.0, src: str = "x.png") -> Mark:
    return Mark(src=src, ar=ar, opaque=opaque)


def test_single_mark_capped_by_zone_height() -> None:
    """One square mark in a wide zone: the stack cap H/(1+gap) binds,
    not the width."""
    b = best_arrangement([_m(1.0)], 400.0, 100.0)
    assert len(b["rows"]) == 1
    assert b["h"] == pytest.approx(100.0 / (1 + ROW_GAP_FRAC))


def test_wide_wordmark_capped_by_width() -> None:
    """An AR-8 wordmark in a 400px-wide zone caps at 400/8 = 50px --
    the bug class the packer exists to prevent (wordmark at full row
    height overflowing the zone)."""
    b = best_arrangement([_m(8.0)], 400.0, 300.0)
    assert b["h"] == pytest.approx(50.0)


def test_two_rows_beat_one_when_width_binds() -> None:
    """Two AR-4 marks side by side are width-starved; stacking them
    doubles the uniform height. The search must find the 2-row split
    and give BOTH rows the same height."""
    b = best_arrangement([_m(4.0), _m(4.0)], 400.0, 400.0)
    assert len(b["rows"]) == 2
    assert b["h"] == pytest.approx(400.0 / 4.0)  # width cap per row
    assert all(h == b["h"] for h in b["row_heights"])


def test_row_gap_subtracted_from_width_budget() -> None:
    """Two marks in ONE row must fit their inter-mark gap too: with
    max_rows=1 forced, h = (W - hgap) / sum_ar, not W / sum_ar."""
    b = best_arrangement([_m(2.0), _m(2.0)], 400.0, 1000.0, max_rows=1)
    assert b["h"] == pytest.approx((400.0 - DEFAULT_HGAP_PX) / 4.0)


def test_uniform_height_never_mixed() -> None:
    """Whatever the partition, every row carries the SAME height --
    marks enlarge together, never some big / some small."""
    b = best_arrangement(
        [_m(1.0), _m(2.6), _m(0.9), _m(3.1)], 800.0, 500.0
    )
    assert len(set(b["row_heights"])) <= 1


def test_empty_zone_degrades() -> None:
    b = best_arrangement([], 400.0, 300.0)
    assert b["rows"] == [] and b["h"] == 0.0


def test_gap_wider_than_zone_is_infeasible_not_clamped() -> None:
    """When the inter-mark gaps alone exceed the zone width, the row is
    infeasible -- no 1px-budget clamp emitting a guaranteed-overflow
    proposal. Two marks with max_rows=1 and a 500px gap in a 400px
    zone must yield NO arrangement (the single-mark-per-row split is
    forced off by max_rows=1)."""
    b = best_arrangement([_m(2.0), _m(2.0)], 400.0, 300.0,
                         max_rows=1, hgap=500.0)
    assert b["rows"] == []
    # ...while allowing 2 rows makes it feasible again (no gaps used).
    b2 = best_arrangement([_m(2.0), _m(2.0)], 400.0, 300.0,
                          max_rows=2, hgap=500.0)
    assert len(b2["rows"]) == 2


def test_degenerate_hgap_sanitized() -> None:
    """NaN / negative hgap falls back to the default instead of
    corrupting the width budget."""
    good = best_arrangement([_m(2.0), _m(2.0)], 400.0, 1000.0, max_rows=1)
    for bad_gap in (float("nan"), -10.0):
        b = best_arrangement([_m(2.0), _m(2.0)], 400.0, 1000.0,
                             max_rows=1, hgap=bad_gap)
        assert b["h"] == pytest.approx(good["h"])


def test_snippet_carries_every_src_and_height() -> None:
    rows = [[_m(1.0, src="a.png"), _m(2.0, src="b.svg")],
            [_m(3.0, src="c.png")]]
    snip = render_snippet(rows, 104.4)
    assert snip.count('<div class="logo-row">') == 2
    for src in ("a.png", "b.svg", "c.png"):
        assert src in snip
    # Height lives in a CSS RULE, never an inline style= (style_check
    # Rule 2 hard-bans inline styles), and rounds DOWN so a width-bound
    # proposal can never overshoot its zone (104.4 -> 104, never 105).
    assert "height: 104px" in snip
    assert "style=" not in snip
    assert render_snippet(rows, 155.6).count("height: 155px") == 1


def test_snippet_row_flex_and_hgap_are_explicit() -> None:
    """The packing math budgets an inter-mark gap; the emitted CSS must
    RENDER that same gap (explicit row flex + gap), or --hgap would
    change the numbers without changing the layout."""
    snip = render_snippet([[_m(2.0), _m(2.0)]], 100.0, hgap=32.0)
    assert ".logo-pack .logo-row { display: flex;" in snip
    assert "gap: 32px" in snip


def test_snippet_uses_template_u_when_measured() -> None:
    """When the probe read the template's --u, lengths ride var(--u)
    (screen preview keeps scaling), truncated inward at 0.1u."""
    snip = render_snippet([[_m(1.0, src="a.png")]], 155.3, u_px=1.6)
    assert "calc(97 * var(--u))" in snip     # 155.3/1.6 = 97.06 -> 97.0
    assert "px;" not in snip.split("<!-- CSS")[1].replace(
        "max-width: none;", "")


def test_snippet_zone_class_disambiguates() -> None:
    snip = render_snippet([[_m(1.0)]], 90.0, cls="logo-pack-2")
    assert '<div class="logo-pack-2">' in snip
    assert ".logo-pack-2 .logo-slot img" in snip


def test_snippet_escapes_src_and_alt() -> None:
    m = Mark(src='data:image/svg+xml;utf8,<svg a="1">', ar=1.0,
             alt='Lab "X" & co')
    snip = render_snippet([[m]], 90.0)
    assert '<svg a="1">' not in snip
    assert "&quot;" in snip and "&amp;" in snip


def test_snippet_keeps_gate_e_contract() -> None:
    """Every mark stays inside a .logo-slot (Gate E only sees
    .logo-slot img), keeps its alt, and carries data-color-exempt so a
    brand-colored mark cannot newly trip the color gate. Multi-row
    proposals stack inside a column wrapper -- NOT nested flex rows
    side by side."""
    rows = [[_m(1.0, src="a.png"), _m(2.0, src="b.png")],
            [_m(3.0, src="c.png")]]
    snip = render_snippet(rows, 100.0)
    assert snip.count('<div class="logo-slot">') == 3
    assert snip.count('data-color-exempt="logo"') == 3
    assert 'alt="Lab A"' in render_snippet(
        [[Mark(src="a.png", ar=1.0, alt="Lab A")]], 100.0
    )
    assert 'class="logo-pack"' in snip
    assert "flex-direction: column" in snip


def test_snippet_inline_svg_gets_comment_not_img() -> None:
    snip = render_snippet([[_m(1.5, src="(inline svg)")]], 90.0)
    assert "<img src=" not in snip     # no fabricated <img> element
    assert "inline <svg> logo" in snip and "height: 90px" in snip
    assert "verify an inline-SVG mark by eye" in snip
