"""Unit tests for the edit-targets helpers in ``_posterly.measure`` --
``source_card_lines`` (source line per card, via preflight's role
scanner) and ``format_edit_targets`` (the printed block). Pure
functions; no Chromium.
"""
from __future__ import annotations

from _posterly.measure import format_edit_targets, source_card_lines


_HTML = """<!DOCTYPE html>
<html><head><title>t</title></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">one</div>
      <div class="card"
           data-measure-role="card">two (attr on continuation line)</div>
    </div>
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">three</div>
    </div>
  </div>
</body></html>
"""


def test_source_card_lines_in_order() -> None:
    lines = source_card_lines(_HTML)
    assert len(lines) == 3
    assert lines == sorted(lines)
    # First card opens on the line containing "one" -- the tag's line.
    assert _HTML.splitlines()[lines[0] - 1].strip().startswith(
        '<div class="card"'
    )


def test_source_card_lines_unparseable_returns_empty() -> None:
    # A truncated/garbage input must yield [] (callers then omit line
    # numbers), never raise.
    assert source_card_lines("") == []


def _cols() -> list[dict]:
    return [{
        "name": "col0",
        "hint": "grow ~44 px [safe +41..+46]",
        "cards": [
            # Deliberately out of DOM order: format sorts by (y, x).
            {"card_idx": 1, "x": 0.0, "y": 700.0, "bottom": 1300.0,
             "h": 600.0, "anchor": "2  Method"},
            {"card_idx": 0, "x": 0.0, "y": 100.0, "bottom": 690.0,
             "h": 590.0, "anchor": "1  Motivation"},
        ],
    }]


def test_format_marks_bottom_card_and_sorts() -> None:
    out = "\n".join(format_edit_targets(_cols(), [12, 40, 80], 3))
    # Sorted top-to-bottom: Motivation first.
    assert out.index("Motivation") < out.index("Method")
    # Only the bottom-most card carries the marker.
    lines = out.splitlines()
    marked = [ln for ln in lines if "<- bottom card" in ln]
    assert len(marked) == 1 and "Method" in marked[0]
    # Line numbers mapped by card ordinal: card#0 -> L12, card#1 -> L40.
    assert "card#0" in out and "L12" in out
    assert "card#1" in out and "L40" in out
    assert "col0 (grow ~44 px [safe +41..+46]):" in out


def test_format_bottom_tie_marks_all() -> None:
    cols = _cols()
    # Second card's bottom within 0.5px of the first -> both marked.
    cols[0]["cards"][1]["bottom"] = 1300.0
    cols[0]["cards"][0]["bottom"] = 1299.8
    out = format_edit_targets(cols, [12, 40, 80], 3)
    marked = [ln for ln in out if "<- bottom card" in ln]
    assert len(marked) == 2


def test_format_omits_lines_on_count_mismatch() -> None:
    """When the source scan found a different number of cards than the
    DOM reported (dynamic markup, parse trouble), the ordinal->line map
    is untrustworthy: print L? rather than a wrong line number."""
    out = "\n".join(format_edit_targets(_cols(), [12, 40], 3))
    assert "L?" in out
    assert "L12" not in out


def test_format_ascii_safe_anchor() -> None:
    cols = _cols()
    cols[0]["cards"][0]["anchor"] = "Méthode → résultats"
    out = "\n".join(format_edit_targets(cols, [12, 40, 80], 3))
    out.encode("ascii")  # must not raise
