"""Alignment + gap-to-strip measurement — the HARD gate.

This is the only gate that decides whether columns visually align. It
print-emulates the HTML in headless Chromium, reads the geometry of
every ``[data-measure-role]`` element, and reports two numbers:

  - **spread**: max−min of last-card-bottoms across all columns
    (plus any hero panel). Aim < 3 px; default fail threshold 5 px.
  - **gap → footer-strip/footer**: distance from the last card's
    bottom to the next horizontal strip. Aim [30, 50] px so card
    shadows clear but cards don't visually float.

Non-negotiables built in: an empty column hard-fails (fallback to
column.bottom is risky); missing footer-strip/footer hard-fails; a
MathJax typeset error / timeout / silent CDN block hard-fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import canvas as _canvas
from . import render as _render


def _eprint(*args: Any, **kw: Any) -> None:
    print(*args, file=sys.stderr, **kw)


_MEASURE_JS = r"""
() => {
  const nodes = Array.from(document.querySelectorAll('[data-measure-role]'));
  return nodes.map(n => {
    const r = n.getBoundingClientRect();
    return {
      role: n.getAttribute('data-measure-role') || '',
      tag:  n.tagName.toLowerCase(),
      cls:  n.className || '',
      x: r.left, y: r.top, w: r.width, h: r.height,
      bottom: r.bottom, right: r.right,
    };
  });
}
"""


def cmd_measure(args: argparse.Namespace) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _eprint("ERROR: playwright not installed. Run:")
        _eprint("  python -m pip install playwright")
        _eprint("  python -m playwright install chromium")
        return 2

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        _eprint(f"ERROR: HTML not found: {html_path}")
        return 2

    resolved = _canvas.resolve_canvas(
        html_path, args.canvas, label="[measure]"
    )
    if resolved is None:
        _eprint(
            "ERROR: could not find `@page { size: <W> <H> }` in HTML. "
            "Add an @page rule (units: in/mm/cm/pt) or pass "
            "`--canvas <W>x<H>in` / `--canvas 'A0 portrait'`. "
            "Refusing to silently fall back."
        )
        return 2
    canvas, viewport = resolved

    with sync_playwright() as p:
        browser, _ctx, page = _render.open_print_emulated_page(p, viewport)
        page.goto(html_path.as_uri(), wait_until="networkidle")

        settle = _render.settle_page(
            page,
            mathjax_timeout_ms=args.mathjax_timeout_ms,
            settle_ms=args.settle_ms,
        )
        fail = _render.hard_fail_on_settle_problems(
            settle, mathjax_timeout_ms=args.mathjax_timeout_ms,
        )
        if fail is not None:
            browser.close()
            _eprint(f"FAIL: {fail}")
            return 1

        data = page.evaluate(_MEASURE_JS)
        browser.close()

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        print(f"[measure] raw data → {args.json_out}")

    # Canvas-fill gate. The `[data-measure-role="poster"]` box must:
    #   (a) exist — otherwise measure has nothing to anchor the layout
    #       against, and a silent PASS would be misleading;
    #   (b) fill the print viewport in BOTH dimensions, within a
    #       tolerance band of [min_canvas_fill, 1/min_canvas_fill]. The
    #       low side catches the common bug where the poster forgets
    #       the `@media print { :root { --u: 1mm } }` override and
    #       renders at screen scale into ~42 % of canvas. The high
    #       side catches the symmetric mistake where the poster CSS
    #       declares dimensions larger than @page.
    poster_box = next((el for el in data if el["role"] == "poster"), None)
    if poster_box is None:
        _eprint(
            "FAIL: no [data-measure-role=\"poster\"] element found on "
            "the page. Add it to the root poster container — measure "
            "needs it to verify the canvas-fill, and preflight already "
            "rejects pages without it."
        )
        return 1
    vw, vh = viewport
    fill_w = poster_box["w"] / vw
    fill_h = poster_box["h"] / vh
    lo = args.min_canvas_fill
    hi = 1.0 / lo if lo > 0 else float("inf")
    if not (lo <= fill_w <= hi) or not (lo <= fill_h <= hi):
        _eprint(
            f"FAIL: [data-measure-role=\"poster\"] fills "
            f"{fill_w * 100:.0f}% × {fill_h * 100:.0f}% of the print "
            f"viewport (target {lo * 100:.0f}% – {hi * 100:.0f}% in "
            f"BOTH dimensions). Common cause when too small: missing "
            f"`@media print {{ :root {{ --u: 1mm }} }}` so the poster "
            f"keeps the screen-mode unit scale in print. Common cause "
            f"when too large: hardcoded `width` exceeds `@page size`."
        )
        return 1

    columns: dict[int, dict[str, Any]] = {}
    heros: list[dict[str, Any]] = []
    footer_strips: list[dict[str, Any]] = []
    footers: list[dict[str, Any]] = []

    col_index = 0
    for el in data:
        role = el["role"]
        if role == "column":
            columns[col_index] = {"box": el, "last_card_bottom": None}
            col_index += 1
        elif role == "hero":
            heros.append(el)
        elif role == "footer-strip":
            footer_strips.append(el)
        elif role == "footer":
            footers.append(el)

    def x_overlaps(card: dict, box: dict) -> bool:
        cx_mid = card["x"] + card["w"] / 2
        return box["x"] <= cx_mid <= box["x"] + box["w"]

    for el in data:
        if el["role"] != "card":
            continue
        for ci, col in columns.items():
            if x_overlaps(el, col["box"]):
                prev = col["last_card_bottom"]
                if prev is None or el["bottom"] > prev:
                    col["last_card_bottom"] = el["bottom"]
                break

    empty_cols = [
        ci for ci, col in columns.items()
        if col["last_card_bottom"] is None
    ]
    if empty_cols and not args.allow_empty_column:
        _eprint(
            f"ERROR: columns with no cards detected: "
            f"{['col' + str(i) for i in empty_cols]}. "
            "Add cards or pass --allow-empty-column."
        )
        return 1

    bottoms: list[tuple[str, float]] = []
    for ci, col in columns.items():
        b = col["last_card_bottom"]
        if b is None:
            b = col["box"]["bottom"]
        bottoms.append((f"col{ci}", b))
    for hi, hero in enumerate(heros):
        bottoms.append(
            (f"hero{hi}" if len(heros) > 1 else "hero", hero["bottom"])
        )

    if not bottoms:
        _eprint(
            "ERROR: no columns or hero found. "
            'Did you add data-measure-role="column"?'
        )
        return 2

    bs = [b for _, b in bottoms]
    spread = max(bs) - min(bs)

    max_bottom = max(bs)

    def _pick_nearest(strips: list[dict[str, Any]],
                      target: float) -> dict[str, Any] | None:
        if not strips:
            return None
        return min(strips, key=lambda s: abs(s["y"] - target))

    if footer_strips:
        next_strip = _pick_nearest(footer_strips, max_bottom)
        next_name = "footer-strip"
    elif footers:
        next_strip = _pick_nearest(footers, max_bottom)
        next_name = "footer"
    else:
        next_strip = None
        next_name = None

    gap_range: tuple[float, float] | None = None
    gaps: list[tuple[str, float]] = []
    if next_strip is not None:
        for name, b in bottoms:
            gaps.append((name, next_strip["y"] - b))
        gap_range = (min(g for _, g in gaps), max(g for _, g in gaps))

    print()
    print(f"[measure] columns found: {len(columns)}"
          + (f" (+ {len(heros)} hero)" if heros else ""))
    for name, b in bottoms:
        print(f"  {name:6s}  last-card-bottom = {b:8.2f} px")
    print(f"  spread = {spread:.2f} px   (target < {args.max_spread} px)")
    if next_strip is not None:
        lo, hi = gap_range  # type: ignore[misc]
        print(f"  gap → {next_name} ∈ [{lo:.2f}, {hi:.2f}] px"
              f"   (target [{args.min_gap}, {args.max_gap}])")
    else:
        print("  gap → (no footer-strip or footer below content)")

    ok = True
    if spread >= args.max_spread:
        _eprint(f"FAIL: spread {spread:.2f} >= max {args.max_spread}")
        ok = False
    if next_strip is not None:
        lo, hi = gap_range  # type: ignore[misc]
        if lo < args.min_gap:
            _eprint(f"FAIL: min gap {lo:.2f} < {args.min_gap}")
            ok = False
        if hi > args.max_gap:
            _eprint(f"FAIL: max gap {hi:.2f} > {args.max_gap}")
            ok = False
    elif not args.allow_no_footer_gap:
        _eprint(
            "FAIL: no footer-strip or footer found below content. "
            "Pass --allow-no-footer-gap to skip this gate."
        )
        ok = False

    if ok:
        print("[measure] PASS")
        return 0
    _eprint("[measure] FAIL — alignment gate not met")
    return 1
