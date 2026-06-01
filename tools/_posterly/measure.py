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
from .textutil import ascii_safe


def _eprint(*args: Any, **kw: Any) -> None:
    print(*args, file=sys.stderr, **kw)


_MEASURE_JS = r"""
() => {
  const nodes = Array.from(document.querySelectorAll('[data-measure-role]'));
  return nodes.map(n => {
    const r = n.getBoundingClientRect();
    const cs = window.getComputedStyle(n);
    return {
      role: n.getAttribute('data-measure-role') || '',
      tag:  n.tagName.toLowerCase(),
      cls:  n.className || '',
      x: r.left, y: r.top, w: r.width, h: r.height,
      bottom: r.bottom, right: r.right,
      // For the content-clipping gate: the computed overflow plus the
      // scroll-vs-client deltas. `overflow != visible` decouples the
      // border-box (read above) from the real content extent; a positive
      // (scroll - client) is content sitting past the box edge that print
      // silently clips. Integer-rounded by the browser, so a small
      // tolerance on the Python side absorbs sub-pixel noise.
      overflow_x: cs.overflowX, overflow_y: cs.overflowY,
      scroll_h: n.scrollHeight, client_h: n.clientHeight,
      scroll_w: n.scrollWidth,  client_w: n.clientWidth,
    };
  });
}
"""


def cmd_measure(args: argparse.Namespace) -> int:
    try:
        from playwright.sync_api import sync_playwright
        from playwright.sync_api import TimeoutError as PWTimeoutError
    except ImportError:
        _eprint("ERROR: playwright not installed. Run:")
        _eprint("  python -m pip install playwright")
        _eprint("  python -m playwright install chromium")
        return 2

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        _eprint(f"ERROR: HTML not found: {ascii_safe(html_path)}")
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
        nav_timed_out = False
        try:
            page.goto(html_path.as_uri(), wait_until="networkidle",
                      timeout=args.mathjax_timeout_ms)
        except PWTimeoutError:
            # Don't raw-traceback on a hung/slow resource. Record it and
            # let settle_page surface a MathJax-specific failure first;
            # otherwise fail-fast below. A HARD gate must NOT measure a
            # poster that never finished loading -- a blocked remote image
            # or web font would otherwise sneak through as a false PASS.
            nav_timed_out = True

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
        if nav_timed_out:
            browser.close()
            _eprint(
                "FAIL: page did not reach network-idle within "
                f"{args.mathjax_timeout_ms} ms; refusing to measure a "
                "partially loaded poster. A blocked/slow remote resource "
                "(CDN image, web font, MathJax) is the usual cause -- "
                "inline assets, or raise --mathjax-timeout-ms."
            )
            return 1

        data = page.evaluate(_MEASURE_JS)
        browser.close()

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        print(f"[measure] raw data -> {ascii_safe(args.json_out)}")

    # Canvas-fill gate (coarse early diagnostic). The position-align
    # check below is the authoritative rule — any poster whose bbox
    # aligns to the page within `--position-tol-px` already fills
    # ≈ 100 % of the canvas. This ratio check fires earlier on two
    # specific failure modes with a more diagnostic error message:
    #   (a) missing `[data-measure-role="poster"]` — measure can't
    #       anchor the layout, so a silent PASS would be misleading;
    #   (b) ratio FAR outside the band (e.g. 42 % when the poster
    #       forgot the `@media print { :root { --u: 1mm } }` override
    #       and rendered at screen scale, or 200 % when hardcoded
    #       `width` exceeded `@page size`). The error message points
    #       at the common print-scale bug.
    # For borderline 95–99 % cases, the position gate is the truth.
    # Safe-area design belongs as internal padding on a full-bleed
    # `.poster`, NOT as a smaller poster (which would clip the bbox
    # alignment check).
    poster_box = next((el for el in data if el["role"] == "poster"), None)
    if poster_box is None:
        _eprint(
            "FAIL: no [data-measure-role=\"poster\"] element found on "
            "the page. Add it to the root poster container -- measure "
            "needs it to verify the canvas-fill, and preflight already "
            "rejects pages without it."
        )
        return 1
    vw, vh = viewport
    fill_w = poster_box["w"] / vw
    fill_h = poster_box["h"] / vh
    lo = args.min_canvas_fill
    hi = args.max_canvas_fill
    if not (lo <= fill_w <= hi) or not (lo <= fill_h <= hi):
        _eprint(
            f"FAIL: [data-measure-role=\"poster\"] fills "
            f"{fill_w * 100:.0f}% x {fill_h * 100:.0f}% of the print "
            f"viewport (target {lo * 100:.0f}% - {hi * 100:.0f}% in "
            f"BOTH dimensions). Common cause when too small: missing "
            f"`@media print {{ :root {{ --u: 1mm }} }}` so the poster "
            f"keeps the screen-mode unit scale in print. Common cause "
            f"when too large: hardcoded `width` exceeds `@page size`."
        )
        return 1
    # Positional check: poster must be anchored to the page's origin
    # within `--position-tol-px`. A `transform: translateX(50 px)` would
    # silently clip the right side of the print PDF; size alone can't
    # see this.
    tol = args.position_tol_px
    pos_problems = []
    if abs(poster_box["x"]) > tol:
        pos_problems.append(f"x={poster_box['x']:.1f} (expected ~= 0)")
    if abs(poster_box["y"]) > tol:
        pos_problems.append(f"y={poster_box['y']:.1f} (expected ~= 0)")
    if abs(poster_box["right"] - vw) > tol:
        pos_problems.append(
            f"right={poster_box['right']:.1f} (expected ~= {vw})"
        )
    if abs(poster_box["bottom"] - vh) > tol:
        pos_problems.append(
            f"bottom={poster_box['bottom']:.1f} (expected ~= {vh})"
        )
    if pos_problems:
        _eprint(
            "FAIL: [data-measure-role=\"poster\"] is not aligned to "
            f"the page (tolerance +/-{tol:.1f} px):\n"
            "  " + ", ".join(pos_problems) + ".\n"
            "Fix: make `.poster` full-bleed in print --\n"
            "  @media print {\n"
            "    .poster   { width: 100%; height: 100%;\n"
            "                margin: 0; padding: 0 }\n"
            "    html,body { margin: 0; padding: 0 }\n"
            "  }\n"
            "Then drop any `transform: translate*` / "
            "`position: absolute` offsets.\n"
            "Also check: put `@media print` AFTER the screen "
            "`.poster` rule."
        )
        return 1

    # Content-clipping gate (HARD). Everything below reads each element's
    # border-box edge -- but `overflow` other than `visible` DECOUPLES that
    # box from the real content extent: anything past the edge is clipped
    # in print and silently lost, while the box (and so every spread/gap
    # number below) still looks clean. The classic trap is a flex
    # card/column/hero: when its overflow is hidden/scroll/auto its
    # `min-height: auto` is floored toward 0, so flexbox shrinks the
    # over-full item back inside its track and clips the overflow -- turning
    # a too-full poster into a false PASS. (A fixed-/max-height box with any
    # non-visible overflow clips the same way, without the flex step.) Catch
    # it directly by comparing scroll-size to client-size on the alignment
    # containers -- the exact roles whose bottoms feed spread/gap below.
    #
    # Scope is deliberately those role containers (card, column, hero), NOT
    # a full-descendant sweep: the latter trips over MathJax's off-screen
    # `<mjx-assistive-mml>` a11y nodes (overflow:hidden, a few px of
    # intrinsic overflow) and would false-fail every math poster. Known
    # limitation: an author-built inner panel that clips via its own
    # `max-height; overflow:hidden` (e.g. a scroll-box around a wide table)
    # is NOT scanned -- only the role container itself. `overflow: visible`
    # is never flagged: that content spills VISIBLY and the existing
    # gap/spread gate already sees the displaced box -- only the *hidden*
    # clip is invisible to it.
    clip_overflows = {"hidden", "clip", "scroll", "auto"}
    clip_problems: list[str] = []
    for el in data:
        if el["role"] not in ("card", "column", "hero"):
            continue
        oy = str(el.get("overflow_y") or "").lower()
        ox = str(el.get("overflow_x") or "").lower()
        dy = el.get("scroll_h", 0) - el.get("client_h", 0)
        dx = el.get("scroll_w", 0) - el.get("client_w", 0)
        axes: list[str] = []
        if oy in clip_overflows and dy > args.max_clip_px:
            axes.append(f"{dy:.0f}px below the box (overflow-y: {oy})")
        if ox in clip_overflows and dx > args.max_clip_px:
            axes.append(f"{dx:.0f}px past the right (overflow-x: {ox})")
        if axes:
            cls = el.get("cls", "")
            ident = f"{el['role']} <{el['tag']}" + (
                f" class=\"{cls}\"" if cls else "") + ">"
            clip_problems.append(f"{ident}: " + ", ".join(axes))
    if clip_problems:
        _eprint(
            "FAIL: content overflows its box and is CLIPPED by "
            "overflow:hidden/clip/scroll/auto -- print drops it silently "
            "while the box still looks aligned:\n"
            + "\n".join("  " + p for p in clip_problems)
            + f"\n(tolerance {args.max_clip_px:.0f} px). Fix: remove the "
            "`overflow` rule so the content overflows VISIBLY -- measure "
            "then reports a negative gap pointing at the real 'too much "
            "content' problem -- then cut content, shrink fonts, or enlarge "
            "the canvas. Do NOT use overflow:hidden to make a too-full "
            "column 'pass': a flex item with overflow other than visible "
            "has min-height auto -> 0, so flexbox shrinks it and clips the "
            "overflow."
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
        print(f"  gap -> {next_name} in [{lo:.2f}, {hi:.2f}] px"
              f"   (target [{args.min_gap}, {args.max_gap}])")
    else:
        print("  gap -> (no footer-strip or footer below content)")

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
    _eprint("[measure] FAIL -- alignment gate not met")
    return 1
