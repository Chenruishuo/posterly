"""Chromium-gated integration test for Gate D (``<br>`` inside a flex box).

A ``<br>`` that is a direct child of a ``display: flex`` / ``inline-flex``
element is blockified into a flex item and stops creating a line break, so
intended multi-line content collapses onto one row. This is a render-time
fact (computed ``display``), invisible to the static preflight scan and to
``measure`` (the card bottom is unchanged) — so it must be exercised against
a real headless Chromium, not the mocked unit suite.

Verifies the gate FIRES on the bug (a non-firing gate is a silent no-op) and
does NOT fire on the correct alternatives (a ``<br>`` in a plain block, or a
flex column built from ``<span>``s with no ``<br>``).

Skipped when Playwright/Chromium isn't installed.
"""
from __future__ import annotations

import argparse

import pytest

from _posterly import polish as _polish


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


def _html(badge: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; box-sizing: border-box; }}
  .flex-row {{ display: flex; align-items: center; }}
  .flex-col {{ display: flex; flex-direction: column; }}
  .block    {{ display: block; }}
</style></head>
<body>
  <div data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">
      {badge}
    </div>
  </div>
  </div>
</body></html>
"""


# The bug: <br> is a direct child of a display:flex element.
_FLEX_BR = '<div class="flex-row">&#8635;<br>repeat<br>iters</div>'
# Correct A: <br> inside a plain block still breaks lines -> no warning.
_BLOCK_BR = '<div class="block">&#8635;<br>repeat<br>iters</div>'
# Correct B: flex column built from spans, no <br> -> no warning.
_FLEX_SPANS = ('<div class="flex-col"><span>&#8635;</span>'
               '<span>repeat</span><span>iters</span></div>')


def _args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200,
        mathjax_timeout_ms=5000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10, strict=False,
    )


def _run(tmp_path, capsys, badge: str) -> str:
    poster = tmp_path / "poster.html"
    poster.write_text(_html(badge), encoding="utf-8")
    rc = _polish.cmd_polish(_args(poster))
    assert rc == 0  # soft gate, warn-only
    return "".join(capsys.readouterr())


def test_flex_br_fires(tmp_path, capsys) -> None:
    out = _run(tmp_path, capsys, _FLEX_BR)
    assert "LAYOUT/FLEX-BR" in out          # the gate must catch the bug
    assert "flex/<br> parents   : 1" in out


def test_block_br_ok(tmp_path, capsys) -> None:
    out = _run(tmp_path, capsys, _BLOCK_BR)
    assert "LAYOUT/FLEX-BR" not in out      # <br> in a plain block is fine


def test_flex_column_spans_ok(tmp_path, capsys) -> None:
    out = _run(tmp_path, capsys, _FLEX_SPANS)
    assert "LAYOUT/FLEX-BR" not in out      # the correct fix must not warn
