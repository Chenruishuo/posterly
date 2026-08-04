"""Chromium-gated integration test for ``measure``'s fast dangling-utility
guard (``_DANGLING_UTIL_JS`` in ``_posterly.measure``).

The iterate loop runs ``measure`` alone between full gate runs, and an
undefined numeric utility (``class="w-93"`` with no ``.w-93`` rule)
silently no-ops there: the ``<img>`` loses its width, the figure
collapses, and the loop chases phantom gap/spread numbers. Three live
posters burned debug rounds this way (w-82/w-88/w-93) even though
style_check rule 14 catches the same defect -- because rule 14 only runs
on full gate rounds. The guard fails ``measure`` itself, before the
geometry probe.

Verifies the guard FIRES on an undefined utility, stays SILENT when the
utility is defined, and honours the logo-subtree exemption (vendor
exports carry arbitrary class names -- same carve-out as style rules
13/14).

Skipped when Playwright/Chromium isn't installed.
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


# Same full-bleed 24x36in skeleton as test_clip_integration: it clears the
# canvas-fill, position, spread and gap gates, so the extra markup/css are
# the only variables the assertions isolate.
def _poster(extra_html: str, extra_css: str) -> str:
    para = ("<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit, "
            "sed do eiusmod tempor incididunt ut labore.</p>")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: flex; flex-direction: column; padding: 60px; }}
  .column {{ flex: 1; display: flex; flex-direction: column; min-height: 0; }}
  .card {{ flex: 1; border: 2px solid #888; padding: 20px;
           display: flex; flex-direction: column; }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233; }}
  p {{ font-size: 28px; line-height: 1.4; }}
  {extra_css}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">
        {para}
        {extra_html}
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
        position_tol_px=2.0, max_clip_px=2.0, json_out=None,
    )


def _run(tmp_path, capsys, extra_html: str, extra_css: str):
    poster = tmp_path / "poster.html"
    poster.write_text(_poster(extra_html, extra_css), encoding="utf-8")
    rc = _measure.cmd_measure(_args(poster))
    return rc, "".join(capsys.readouterr())


def test_dangling_utility_fails_fast(tmp_path, capsys) -> None:
    # class="w-93" with no .w-93 rule -> hard fail naming the token,
    # BEFORE any gap/spread verdict.
    rc, out = _run(tmp_path, capsys, '<div class="w-93">x</div>', "")
    assert rc == 1
    assert "w-93" in out
    assert "no matching CSS rule" in out


def test_defined_utility_and_logo_exemption_pass(tmp_path, capsys) -> None:
    # A defined utility passes; a utility-shaped class on a logo-exempt
    # element is skipped (vendor exports carry arbitrary class names).
    extra_html = ('<div class="w-60">x</div>'
                  '<span data-color-exempt="logo" class="w-77">mark</span>')
    rc, out = _run(tmp_path, capsys, extra_html, ".w-60 { width: 60%; }")
    assert rc == 0
    assert "no matching CSS rule" not in out
