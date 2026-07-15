"""Chromium-gated lifecycle test for ``fit-logos`` re-runs: first probe
-> apply the proposal (simulated) -> re-run.

Pins the discovery + idempotency contract:

  * an APPLIED pack's inner ``.logo-row``s must never be discovered as
    zones (they'd shadow the real outer zone and propose against the
    collapsed strip);
  * a ``data-lf-h0`` stamp on the zone is read back (``max(stamp,
    live)``) and reported;
  * an applied-but-unstamped zone draws the collapsed-height WARN.

Skipped when Playwright/Chromium isn't installed.
"""
from __future__ import annotations

import argparse
import base64
from pathlib import Path

import pytest

from _posterly import fitlogos as _fitlogos

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

_ORIGINAL = """<!doctype html><html><head><style>
@page { size: 20in 10in; }
.header { width: 1000px; }
.logo-row { display: flex; gap: 20px; }
.logo-slot img { height: 40px; width: auto; }
.logo-pack { display: flex; flex-direction: column; }
.logo-pack .logo-slot img { height: 30px; }
</style></head><body>
<div class="poster" data-measure-role="poster">
 <div class="header">
  <div class="logo-row"%(zone_attrs)s>
   %(zone_inner)s
  </div>
 </div>
</div></body></html>"""

_PLAIN_INNER = ('<div class="logo-slot"><img src="a.png"></div>'
                '<div class="logo-slot"><img src="b.png"></div>')

_APPLIED_INNER = """<div class="logo-pack">
  <div class="logo-row"><div class="logo-slot"><img src="a.png"></div></div>
  <div class="logo-row"><div class="logo-slot"><img src="b.png"></div></div>
</div>"""


@pytest.fixture
def chromium():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
    except Exception:
        pytest.skip("Playwright/Chromium not available")


def _run(tmp_path: Path, zone_attrs: str, zone_inner: str, capsys) -> str:
    f = tmp_path / "poster.html"
    f.write_text(_ORIGINAL % {"zone_attrs": zone_attrs,
                              "zone_inner": zone_inner},
                 encoding="utf-8")
    (tmp_path / "a.png").write_bytes(_PNG)
    (tmp_path / "b.png").write_bytes(_PNG)
    rc = _fitlogos.cmd_fit_logos(argparse.Namespace(
        html=str(f), canvas=None, zone=None, max_rows=3, hgap=None,
        settle_ms=100, mathjax_timeout_ms=15000,
    ))
    assert rc == 0
    return capsys.readouterr().out


def test_first_probe_finds_one_zone(chromium, tmp_path, capsys) -> None:
    out = _run(tmp_path, "", _PLAIN_INNER, capsys)
    assert out.count("zone '") == 1
    assert "proposal" in out


def test_rerun_on_stamped_applied_zone(chromium, tmp_path, capsys) -> None:
    """After applying, the OUTER stamped zone is the one (and only)
    zone: the pack's inner .logo-row fallbacks are excluded, and the
    stamp height is packed against."""
    out = _run(tmp_path, ' data-lf-h0="200"', _APPLIED_INNER, capsys)
    assert out.count("zone '") == 1
    assert "taken from the data-lf-h0 stamp" in out
    assert "(1000x200px" in out


def test_rerun_on_unstamped_applied_zone_warns(
        chromium, tmp_path, capsys) -> None:
    out = _run(tmp_path, "", _APPLIED_INNER, capsys)
    assert out.count("zone '") == 1
    assert "no data-lf-h0 stamp" in out


_TWO_ZONES = """<!doctype html><html><head><style>
@page { size: 20in 10in; }
.header { width: 1000px; }
.logo-row { display: flex; gap: 20px; }
.logo-slot img { height: 40px; width: auto; }
.logo-pack { display: flex; flex-direction: column; }
.logo-pack .logo-slot img { height: 30px; }
</style></head><body>
<div class="poster" data-measure-role="poster">
 <div class="header">
  <div class="logo-row" data-lf-h0="200">%(applied)s</div>
  <div class="logo-row">%(plain)s</div>
 </div>
</div></body></html>"""


def test_mixed_stamped_and_plain_zones_both_found(
        chromium, tmp_path, capsys) -> None:
    """A half-applied poster (zone A applied+stamped, zone B untouched)
    must report BOTH zones -- the stamp tier is a union with the row
    fallback, not globally exclusive."""
    f = tmp_path / "poster.html"
    f.write_text(_TWO_ZONES % {"applied": _APPLIED_INNER,
                               "plain": _PLAIN_INNER},
                 encoding="utf-8")
    (tmp_path / "a.png").write_bytes(_PNG)
    (tmp_path / "b.png").write_bytes(_PNG)
    rc = _fitlogos.cmd_fit_logos(argparse.Namespace(
        html=str(f), canvas=None, zone=None, max_rows=3, hgap=None,
        settle_ms=100, mathjax_timeout_ms=15000,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("zone '") == 2
    assert "taken from the data-lf-h0 stamp" in out   # zone A used it


def test_explicit_zone_zero_match_never_falls_back(
        chromium, tmp_path, capsys) -> None:
    """--zone is a real override: zero matches is REPORTED, not
    silently replaced by an auto-discovered zone."""
    f = tmp_path / "poster.html"
    f.write_text(_ORIGINAL % {"zone_attrs": "", "zone_inner": _PLAIN_INNER},
                 encoding="utf-8")
    (tmp_path / "a.png").write_bytes(_PNG)
    (tmp_path / "b.png").write_bytes(_PNG)
    rc = _fitlogos.cmd_fit_logos(argparse.Namespace(
        html=str(f), canvas=None, zone="#does-not-exist", max_rows=3,
        hgap=None, settle_ms=100, mathjax_timeout_ms=15000,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    assert "matched no measurable logo zone" in out
    assert "mark(s)" not in out       # the .logo-row was NOT auto-used


def test_explicit_zone_overrides_data_logo_zone(
        chromium, tmp_path, capsys) -> None:
    """--zone wins over an in-document [data-logo-zone] marker."""
    html = _ORIGINAL % {"zone_attrs": ' data-logo-zone="main"',
                        "zone_inner": _PLAIN_INNER}
    html = html.replace(
        "</div>\n </div>\n</div></body>",
        '</div>\n  <div id="alt" class="logo-row">'
        '<div class="logo-slot"><img src="b.png"></div></div>\n'
        " </div>\n</div></body>")
    f = tmp_path / "poster.html"
    f.write_text(html, encoding="utf-8")
    (tmp_path / "a.png").write_bytes(_PNG)
    (tmp_path / "b.png").write_bytes(_PNG)
    rc = _fitlogos.cmd_fit_logos(argparse.Namespace(
        html=str(f), canvas=None, zone="#alt", max_rows=3, hgap=None,
        settle_ms=100, mathjax_timeout_ms=15000,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("zone '") == 1
    assert "1 mark(s)" in out         # #alt has ONE img; the marked
    assert "2 mark(s)" not in out     # data-logo-zone (2 imgs) was skipped


def test_stamped_zone_plus_standalone_slot_both_found(
        chromium, tmp_path, capsys) -> None:
    """The auto union covers all three sources: a stamped zone AND a
    standalone .logo-slot (no row around it) both surface."""
    html = _TWO_ZONES % {"applied": _APPLIED_INNER, "plain": ""}
    html = html.replace(
        '<div class="logo-row"></div>',
        '<div class="logo-slot"><img src="b.png"></div>')
    f = tmp_path / "poster.html"
    f.write_text(html, encoding="utf-8")
    (tmp_path / "a.png").write_bytes(_PNG)
    (tmp_path / "b.png").write_bytes(_PNG)
    rc = _fitlogos.cmd_fit_logos(argparse.Namespace(
        html=str(f), canvas=None, zone=None, max_rows=3, hgap=None,
        settle_ms=100, mathjax_timeout_ms=15000,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("zone '") == 2
    assert "taken from the data-lf-h0 stamp" in out


def test_inner_stamped_zone_beats_outer_fallback_row(
        chromium, tmp_path, capsys) -> None:
    """Priority-aware overlap resolution: a zone that was --zone-picked
    and stamped INSIDE a .logo-row must win over the fallback row
    around it -- keeping the outer would bypass the stamp again."""
    inner = ('<div class="inzone" data-lf-h0="150">'
             '<div class="logo-slot"><img src="a.png"></div>'
             '<div class="logo-slot"><img src="b.png"></div></div>')
    f = tmp_path / "poster.html"
    f.write_text(_ORIGINAL % {"zone_attrs": "", "zone_inner": inner},
                 encoding="utf-8")
    (tmp_path / "a.png").write_bytes(_PNG)
    (tmp_path / "b.png").write_bytes(_PNG)
    rc = _fitlogos.cmd_fit_logos(argparse.Namespace(
        html=str(f), canvas=None, zone=None, max_rows=3, hgap=None,
        settle_ms=100, mathjax_timeout_ms=15000,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("zone '") == 1
    assert "zone 'inzone'" in out                     # the stamped inner won
    assert "taken from the data-lf-h0 stamp" in out


def test_empty_zone_selector_refused(tmp_path, capsys) -> None:
    """--zone '' must be refused (exit 2), not silently re-enter
    automatic discovery. Browser-free: the guard fires before launch."""
    f = tmp_path / "poster.html"
    f.write_text("<html></html>", encoding="utf-8")
    rc = _fitlogos.cmd_fit_logos(argparse.Namespace(
        html=str(f), canvas=None, zone="  ", max_rows=3, hgap=None,
        settle_ms=100, mathjax_timeout_ms=15000,
    ))
    assert rc == 2


def test_eliminated_row_does_not_drag_down_sibling_slot(
        chromium, tmp_path, capsys) -> None:
    """Greedy, not pairwise-simultaneous, overlap resolution: a row
    knocked out by the stamped div in ONE of its branches must not also
    eliminate the untouched sibling .logo-slot in its OTHER branch."""
    inner = ('<div class="inzone" data-lf-h0="150">'
             '<div class="logo-slot"><img src="a.png"></div></div>'
             '<div class="logo-slot"><img src="b.png"></div>')
    f = tmp_path / "poster.html"
    f.write_text(_ORIGINAL % {"zone_attrs": "", "zone_inner": inner},
                 encoding="utf-8")
    (tmp_path / "a.png").write_bytes(_PNG)
    (tmp_path / "b.png").write_bytes(_PNG)
    rc = _fitlogos.cmd_fit_logos(argparse.Namespace(
        html=str(f), canvas=None, zone=None, max_rows=3, hgap=None,
        settle_ms=100, mathjax_timeout_ms=15000,
    ))
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("zone '") == 2          # stamp branch AND sibling slot
    assert "zone 'inzone'" in out
    assert "zone 'logo-slot'" in out         # the sibling slot survived
    assert "zone 'logo-row'" not in out      # the outer row did NOT win
    assert "taken from the data-lf-h0 stamp" in out
