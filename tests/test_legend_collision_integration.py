"""Tests for the protruding-content collision gate in ``measure``.

Real-world failure this pins (Codex-authored ICML poster, 2026-08-03):
the agent chose the Axis-7 "fieldset-legend" heading joint and
implemented it as a hand-tuned ``margin-top: calc(-19 * var(--u))`` on
``.section-title``. The pull-up was calibrated to a one-line title and
reserved no room for the protruding half, so every column's title
chip landed ~30 px (print scale) INSIDE the framework banner above --
plainly overprinted in the PDF -- while every existing measure gate
passed: spread/gap/intercard read card border-boxes, the clip gate only
sees overflow HIDDEN by the box, and canvas-overflow only sees
right/bottom spill past the poster root.

The fix: each card reports the raw bboxes of its layout-visible escaped
descendants (``prot_boxes``); measure hard-fails when the outside-card
fragment of any box reaches into a non-ancestor sibling section (header,
banner, another card, ...) by more than ``--max-collision-px`` on both
axes.

Verifies the gate FIRES on the negative-margin legend overprinting a
banner, stays SILENT on the sanctioned ``card--legend`` recipe
(translateY(-50%) straddle + card margin-top clearance), and skips
ancestor containment. Chromium cases are skipped when
Playwright/Chromium isn't installed; the pure-function cases always run.
"""
from __future__ import annotations

import argparse
import json

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


_CHROMIUM = pytest.mark.skipif(
    not _chromium_available(),
    reason="playwright + chromium not available",
)


# ---------------------------------------------------------------------------
# Pure-function cases (no Chromium)
# ---------------------------------------------------------------------------

def _box(role, x, y, right, bottom, **extra):
    d = {
        "role": role, "tag": "div", "cls": extra.pop("cls", ""),
        "anchor": extra.pop("anchor", ""), "card_idx": extra.pop("idx", -1),
        "node_idx": extra.pop("node_idx", -1),
        "ancestor_node_idxs": extra.pop("ancestor_node_idxs", []),
        "x": x, "y": y, "w": right - x, "h": bottom - y,
        "right": right, "bottom": bottom,
        "prot_boxes": extra.pop("prot_boxes", []),
    }
    d.update(extra)
    return d


def _prot(left, top, right, bottom, cls="section-title"):
    return {"top": top, "left": left, "right": right, "bottom": bottom,
            "tag": "div", "cls": cls}


def test_protruding_title_into_banner_fires() -> None:
    banner = _box("banner", 0, 0, 1000, 200, cls="framework-banner")
    card = _box(
        "card", 0, 220, 480, 900,
        idx=0, anchor="1 Why trajectory structure?",
        # title chip pulled 50 px above the card -> 30 px into the banner
        prot_boxes=[_prot(20, 170.0, 420, 210.0)],
    )
    probs = _measure.protrusion_collisions([banner, card], tol=3.0)
    assert len(probs) == 1
    assert "card#0" in probs[0]
    assert "Why trajectory structure?" in probs[0]
    assert "section-title" in probs[0]
    assert "above" in probs[0]
    assert "banner" in probs[0]


def test_protrusion_into_reserved_clearance_silent() -> None:
    # Same protrusion, but the card sits low enough that the escaped
    # chip stays in reserved whitespace -- exactly what the card--legend
    # recipe's margin-top buys. No collision.
    banner = _box("banner", 0, 0, 1000, 200)
    card = _box("card", 0, 280, 480, 900,
                prot_boxes=[_prot(20, 230.0, 420, 300.0)])
    assert _measure.protrusion_collisions([banner, card], tol=3.0) == []


def test_no_phantom_collision_outside_escape_box() -> None:
    # The reason collisions are tested per escaped box, not as one
    # union rectangle: a chip riding the card's top-LEFT must not
    # collide with a neighbour that only faces the card's RIGHT half.
    right_banner = _box("banner", 500, 0, 1000, 260)
    card = _box("card", 0, 280, 480, 900,
                prot_boxes=[_prot(20, 230.0, 200, 300.0)])
    assert _measure.protrusion_collisions([right_banner, card], tol=3.0) == []


def test_dom_ancestor_skipped() -> None:
    # DOM ancestry, not similar geometry, establishes containment.
    band = _box("band", 0, 0, 1000, 1000, node_idx=4)
    card = _box("card", 100, 300, 900, 800,
                node_idx=7, ancestor_node_idxs=[4],
                prot_boxes=[_prot(120, 260.0, 500, 330.0)])
    assert _measure.protrusion_collisions([band, card], tol=3.0) == []


def test_geometric_container_sibling_not_mistaken_for_ancestor() -> None:
    # A positioned sibling can geometrically contain the whole card. It
    # is still a neighbour and must not inherit an ancestor exemption.
    sibling = _box("hero", 0, 0, 1000, 1000, node_idx=4)
    card = _box(
        "card", 100, 300, 900, 800,
        node_idx=7, ancestor_node_idxs=[],
        prot_boxes=[_prot(120, 260.0, 500, 330.0)],
    )
    probs = _measure.protrusion_collisions([sibling, card], tol=3.0)
    assert len(probs) == 1
    assert "hero" in probs[0]


def test_only_the_escaped_fragment_can_collide() -> None:
    # The title escapes above, but this measured neighbour intersects
    # only the part of its bbox that remains inside the card. Testing the
    # full descendant bbox would be a false protrusion-collision report.
    neighbour = _box("banner", 20, 230, 420, 290)
    card = _box(
        "card", 0, 220, 480, 900,
        prot_boxes=[_prot(20, 170.0, 420, 290.0)],
    )
    assert _measure.protrusion_collisions([neighbour, card], tol=3.0) == []


def test_intercard_gap_uses_protruding_title_edge() -> None:
    # Border boxes are 68 px apart, which would exceed the 50 px void
    # ceiling. The lower card's title occupies 42 px of that clearance,
    # leaving a normal 26 px visible gap.
    upper = _box("card", 0, 0, 480, 500)
    lower = _box(
        "card", 0, 568, 480, 900,
        prot_boxes=[_prot(20, 526.0, 420, 590.0)],
    )
    assert _measure.intercard_gaps([upper, lower]) == [26.0]


def test_no_protrusion_costs_nothing() -> None:
    banner = _box("banner", 0, 0, 1000, 200)
    card = _box("card", 0, 201, 480, 900)  # box kisses the banner (1 px)
    assert _measure.protrusion_collisions([banner, card], tol=3.0) == []


def test_missing_prot_boxes_tolerated() -> None:
    # Old JSON dumps (pre-gate) lack prot_boxes; treated as no escapes.
    card = {
        "role": "card", "tag": "div", "cls": "", "anchor": "", "card_idx": 0,
        "x": 0, "y": 300, "w": 480, "h": 600, "right": 480, "bottom": 900,
    }
    banner = _box("banner", 0, 0, 1000, 200)
    assert _measure.protrusion_collisions([banner, card], tol=3.0) == []


# ---------------------------------------------------------------------------
# Chromium integration cases
# ---------------------------------------------------------------------------

# Full-bleed 24x36in poster (viewport 2304x3456 px at 96 ppi): banner,
# one flex column with two cards (the last grows so the footer gap
# lands in band), footer strip. `title_css` is the only variable.
def _poster(title_css: str, card_css: str = "") -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 36in; margin: 0; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; background: #fff; }}
  .poster {{ width: 24in; height: 36in; background: #fff;
             display: flex; flex-direction: column; padding: 60px; }}
  .banner {{ height: 300px; background: #eee; border: 2px solid #888;
             margin-bottom: 24px; }}
  .column {{ flex: 1; display: flex; flex-direction: column; gap: 24px; }}
  .card {{ border: 2px solid #888; padding: 20px; }}
  .card.grow {{ flex-grow: 1; }}
  .section-title {{ font-size: 28px; font-weight: bold;
                    background: #fff; width: max-content;
                    display: flex; align-items: center; gap: 10px;
                    padding: 0 10px; {title_css} }}
  .section-title .num {{ width: 44px; height: 44px; border-radius: 50%;
                         display: inline-flex; align-items: center;
                         justify-content: center; background: #ddd; }}
  .card {{ {card_css} }}
  .footer-strip {{ height: 160px; margin-top: 40px; background: #233; }}
  p {{ font-size: 28px; line-height: 1.4; }}
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
    <div class="banner" data-measure-role="banner"></div>
    <div class="column" data-measure-role="column">
      <div class="card" data-measure-role="card">
        <div class="section-title"><span class="num">1</span>
          <span class="st-text">Legend title</span></div>
        <p data-measure-role="probe-body">Card one body text.</p>
      </div>
      <div class="card grow" data-measure-role="card">
        <div class="section-title"><span class="num">2</span>
          <span class="st-text">Second legend</span></div>
        <p>Card two.</p>
      </div>
    </div>
    <div class="footer-strip" data-measure-role="footer-strip"></div>
  </div>
</body></html>
"""


def _args(html, json_out=None) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None,
        max_spread=5.0, min_gap=30.0, max_gap=50.0,
        allow_empty_column=False, allow_no_footer_gap=False,
        settle_ms=200, mathjax_timeout_ms=5000,
        min_canvas_fill=0.95, max_canvas_fill=1.01,
        position_tol_px=2.0, max_clip_px=2.0,
        max_intercard_gap=50.0, min_intercard_gap=12.0,
        max_collision_px=3.0, json_out=json_out,
    )


def _run(tmp_path, capsys, html: str):
    poster = tmp_path / "poster.html"
    raw_data = tmp_path / "measure.json"
    poster.write_text(html, encoding="utf-8")
    rc = _measure.cmd_measure(_args(poster, str(raw_data)))
    data = json.loads(raw_data.read_text(encoding="utf-8"))
    return rc, "".join(capsys.readouterr()), data


@_CHROMIUM
def test_negative_margin_legend_fires(tmp_path, capsys) -> None:
    # The field failure: title pulled 80 px up with a hand-tuned
    # negative margin, banner flush above (banner margin-bottom 24 px,
    # 80 px pull-up minus 22 px border+padding -> ~34 px inside the
    # banner). Hard-fail, and the message points at the sanctioned recipe.
    rc, out, _data = _run(tmp_path, capsys, _poster("margin-top: -80px;"))
    assert rc == 1
    assert "overlaps" in out
    assert "banner" in out
    assert "card--legend" in out


@_CHROMIUM
def test_card_legend_recipe_passes(tmp_path, capsys) -> None:
    # The catalogued recipe: the title straddles the border via
    # translateY(-50%) after a constant relative top cancels border+padding
    # (2 px border + 20 px padding here), and the card reserves the
    # protruding half via margin-top. The chip escapes into RESERVED
    # space only -> no collision complaint, and measure passes.
    rc, out, data = _run(
        tmp_path, capsys,
        _poster(
            "position: relative; top: -22px; transform: translateY(-50%);",
            card_css="margin-top: 30px;",
        ),
    )
    assert rc == 0
    assert "PASS" in out
    assert "overlaps" not in out
    cards = sorted(
        (el for el in data if el["role"] == "card"),
        key=lambda el: el["y"],
    )
    card = cards[0]
    assert cards[1]["y"] - card["bottom"] > 50.0
    assert _measure.intercard_gaps(cards) == pytest.approx([32.0], abs=0.5)
    column = next(el for el in data if el["role"] == "column")
    assert column["node_idx"] in card["ancestor_node_idxs"]
    title = next(
        box for box in card["prot_boxes"]
        if "section-title" in box["cls"].split()
    )
    assert title["top"] < card["y"] < title["bottom"]
    body = next(el for el in data if el["role"] == "probe-body")
    assert body["y"] == pytest.approx(card["y"] + 66.0, abs=0.5)
