"""Static guard: every shipped ``*_neutral.html`` template pins the
``.poster`` grid's column axis with ``grid-template-columns: minmax(0, ...)``.

Dropping it lets the implicit ``auto`` column grow to a wide child's
max-content, so a full-width row overflows the canvas and its right strip
is sliced off in print (measure's canvas-overflow gate). This is a
pure-text assertion -- no Chromium needed -- so it guards the templates
even in environments where the Chromium-gated integration suite is
skipped.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_TEMPLATES = [
    "portrait_2col_neutral.html",
    "landscape_4col_neutral.html",
    "landscape_hero_neutral.html",
]
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


@pytest.mark.parametrize("name", _TEMPLATES)
def test_poster_grid_pins_column_axis(name: str) -> None:
    css = (_TEMPLATE_DIR / name).read_text(encoding="utf-8")
    assert "grid-template-columns: minmax(0, 1fr)" in css, (
        f"{name}: the `.poster` grid must pin its column axis with "
        "`grid-template-columns: minmax(0, 1fr)`; without it a wide child "
        "grows the implicit `auto` column past the canvas and the right "
        "strip is clipped in print (measure's canvas-overflow gate)."
    )
