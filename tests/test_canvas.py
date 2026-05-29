"""Canvas parsing: CLI argument forms + ``@page`` extraction."""
from __future__ import annotations

import argparse

import pytest

from _posterly import canvas


# ---- parse_canvas_arg ------------------------------------------------------

@pytest.mark.parametrize("s,expected", [
    ("60x36in",       (60.0, 36.0)),
    ("24x36in",       (24.0, 36.0)),
    ("60×36in",       (60.0, 36.0)),       # unicode × accepted
    ("36X47IN",       (36.0, 47.0)),       # case-insensitive unit
    ("914x1194mm",    (914 / 25.4, 1194 / 25.4)),
    ("21x29.7cm",     (21 / 2.54, 29.7 / 2.54)),
    ("4320x3240pt",   (4320 / 72.0, 3240 / 72.0)),
])
def test_parse_numeric_dimensions(s: str, expected: tuple[float, float]) -> None:
    w, h = canvas.parse_canvas_arg(s)
    assert w == pytest.approx(expected[0])
    assert h == pytest.approx(expected[1])


@pytest.mark.parametrize("s,exp_mm", [
    ("A0 portrait",  (841,  1189)),
    ("A0 landscape", (1189, 841)),
    ("A1 portrait",  (594,  841)),
    ("A2 portrait",  (420,  594)),
    ("A3 landscape", (420,  297)),
    ("a4 portrait",  (210,  297)),     # case-insensitive name
    ("A0",           (841,  1189)),    # orientation defaults to portrait
])
def test_parse_named_sizes(s: str, exp_mm: tuple[float, float]) -> None:
    w, h = canvas.parse_canvas_arg(s)
    assert w == pytest.approx(exp_mm[0] / 25.4)
    assert h == pytest.approx(exp_mm[1] / 25.4)


@pytest.mark.parametrize("s", [
    "60x36",          # no unit
    "60x36inches",    # wrong unit
    "B0 portrait",    # not in ISO 216 set we support
    "A0 sideways",    # bad orientation
    "60",             # only one dim
    "60x36in extra",  # trailing garbage
    "",
])
def test_parse_rejects_bad_inputs(s: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        canvas.parse_canvas_arg(s)


# ---- read_canvas_from_html -------------------------------------------------

def _write(tmp_path, name: str, body: str):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_read_canvas_inches(tmp_path) -> None:
    p = _write(tmp_path, "a.html", """
        <html><head><style>
          @page { size: 60in 36in; margin: 0; }
        </style></head><body></body></html>
    """)
    assert canvas.read_canvas_from_html(p) == pytest.approx((60.0, 36.0))


def test_read_canvas_mixed_units(tmp_path) -> None:
    """A poster declaring a width in inches and a height in mm should
    still parse correctly — the regex allows the two units to differ."""
    p = _write(tmp_path, "a.html", """
        <html><head><style>
          @page { size: 24in 914mm; }
        </style></head></html>
    """)
    w, h = canvas.read_canvas_from_html(p)
    assert w == pytest.approx(24.0)
    assert h == pytest.approx(914 / 25.4)


def test_read_canvas_ignores_commented_out_rule(tmp_path) -> None:
    """A commented-out @page should NOT be picked up by the parser —
    otherwise users tweaking sizes leave behind silent traps."""
    p = _write(tmp_path, "a.html", """
        <html><head><style>
          /* @page { size: 100in 100in; } */
          @page { size: 36in 47in; }
        </style></head></html>
    """)
    assert canvas.read_canvas_from_html(p) == pytest.approx((36.0, 47.0))


def test_read_canvas_only_inside_style_blocks(tmp_path) -> None:
    """`@page` appearing in body text or scripts must not match — only
    real CSS inside <style> blocks counts."""
    p = _write(tmp_path, "a.html", """
        <html><head>
          <script>const text = "@page { size: 99in 99in }";</script>
        </head><body>@page { size: 50in 50in }</body></html>
    """)
    assert canvas.read_canvas_from_html(p) is None


def test_read_canvas_named_page(tmp_path) -> None:
    """`@page poster { size: ... }` (named page) should match too."""
    p = _write(tmp_path, "a.html", """
        <html><head><style>
          @page poster { size: 36in 47in; margin: 0; }
        </style></head></html>
    """)
    assert canvas.read_canvas_from_html(p) == pytest.approx((36.0, 47.0))


def test_read_canvas_named_size(tmp_path) -> None:
    """CSS Paged Media named-size form must work in the HTML too —
    earlier the parser supported it only on the `--canvas` CLI arg."""
    p = _write(tmp_path, "a.html", """
        <html><head><style>
          @page { size: A1 portrait; margin: 0; }
        </style></head></html>
    """)
    w, h = canvas.read_canvas_from_html(p)
    assert w == pytest.approx(594 / 25.4)
    assert h == pytest.approx(841 / 25.4)


def test_read_canvas_named_size_landscape(tmp_path) -> None:
    p = _write(tmp_path, "a.html", """
        <html><head><style>
          @page { size: A0 landscape; }
        </style></head></html>
    """)
    w, h = canvas.read_canvas_from_html(p)
    assert w == pytest.approx(1189 / 25.4)
    assert h == pytest.approx(841 / 25.4)


def test_read_canvas_named_size_defaults_portrait(tmp_path) -> None:
    """`size: A0;` (no explicit orientation) → portrait."""
    p = _write(tmp_path, "a.html", """
        <html><head><style>
          @page { size: A0; }
        </style></head></html>
    """)
    w, h = canvas.read_canvas_from_html(p)
    assert w == pytest.approx(841 / 25.4)
    assert h == pytest.approx(1189 / 25.4)


def test_read_canvas_returns_none_when_missing(tmp_path) -> None:
    p = _write(tmp_path, "a.html",
               "<html><head><style>body { color: red }</style></head></html>")
    assert canvas.read_canvas_from_html(p) is None


# ---- viewport_for ----------------------------------------------------------

def test_viewport_at_96_ppi() -> None:
    assert canvas.viewport_for((60.0, 36.0)) == (5760, 3456)
    assert canvas.viewport_for((24.0, 36.0)) == (2304, 3456)
    # A0 portrait ~ 33.11 × 46.81 in.
    w, h = canvas.viewport_for(canvas.parse_canvas_arg("A0 portrait"))
    assert w == pytest.approx(33.11 * 96, abs=2)
    assert h == pytest.approx(46.81 * 96, abs=2)
