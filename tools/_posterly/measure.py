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
import math
import sys
from pathlib import Path
from typing import Any

from . import budget as _budget
from . import canvas as _canvas
from . import polish as _polish
from . import render as _render
from .textutil import ascii_safe


def _eprint(*args: Any, **kw: Any) -> None:
    print(*args, file=sys.stderr, **kw)


#: Hard ceiling for the whitespace between consecutive stacked cards in a
#: column. Same ceiling as the footer gap: anything wider reads as a void
#: in print. Shared by the CLI default in poster_check.py and the getattr
#: fallback in cmd_measure.
DEFAULT_MAX_INTERCARD_GAP = 50.0

#: Hard floor for the same gap. The shipped card shadow is
#: ``0 2u 6u`` (offset ~7.6 px + blur ~22.7 px at print scale, u = 1mm);
#: a gap under ~12 px buries the shadow core under the next card, so the
#: stack reads as one fused slab instead of separate cards. Floor sits
#: well under the shipped 6u (~22.7 px) design gap; tune (or 0 to
#: disable) for shadowless custom themes.
DEFAULT_MIN_INTERCARD_GAP = 12.0


def intercard_gaps(cards: list[dict]) -> list[float]:
    """Vertical gaps between consecutive *rows* of cards in one column.

    Cards are grouped into rows by vertical-overlap chaining (sorted by
    top; a card whose top sits above the current row's bottom joins that
    row), so two half-width cards sitting side by side count as ONE row
    and don't produce a bogus negative/huge "gap". Returns one gap per
    consecutive row pair. Pure function so the grouping rule is
    unit-testable without Chromium.
    """
    if len(cards) < 2:
        return []
    rows: list[list[float]] = []  # [top, bottom] per row
    for c in sorted(cards, key=lambda c: c["y"]):
        if rows and c["y"] < rows[-1][1]:
            rows[-1][1] = max(rows[-1][1], c["bottom"])
        else:
            rows.append([c["y"], c["bottom"]])
    return [rows[i][0] - rows[i - 1][1] for i in range(1, len(rows))]


_MEASURE_JS = r"""
() => {
  const nodes = Array.from(document.querySelectorAll('[data-measure-role]'));
  let cardOrdinal = 0;
  return nodes.map(n => {
    const r = n.getBoundingClientRect();
    const cs = window.getComputedStyle(n);
    const role = n.getAttribute('data-measure-role') || '';
    // Edit-target anchor for cards: the section-title text (fallback:
    // the card's own text), with MathJax containers stripped -- typeset
    // math mutates the DOM, so its innerText would not match the source
    // HTML the agent greps. This is a LOCATOR, not verbatim source.
    let anchor = '';
    let cardIdx = -1;
    if (role === 'card') {
      cardIdx = cardOrdinal++;
      const src = n.querySelector('.section-title') || n;
      const clone = src.cloneNode(true);
      clone.querySelectorAll(
        'mjx-container, mjx-assistive-mml, script, style'
      ).forEach(e => e.remove());
      anchor = (clone.textContent || '')
        .replace(/\s+/g, ' ').trim().slice(0, 60);
    }
    return {
      role: role,
      tag:  n.tagName.toLowerCase(),
      cls:  n.className || '',
      anchor: anchor,
      card_idx: cardIdx,
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


def compute_adjustment_hints(
    bottoms: list[tuple[str, float]],
    strip_top: float,
    *,
    min_gap: float,
    max_gap: float,
    max_spread: float,
    epsilon: float = 0.5,
) -> tuple[tuple[float, float], list[tuple[str, float, str]]]:
    """Per-column adjustment hints for a failed measure run.

    Returns ``((band_lo, band_hi), adjustments)`` where ``adjustments``
    is one ``(name, current_bottom, hint)`` per column / hero row.

    ``[band_lo, band_hi]`` is the **shared passing band**: when every
    column bottom lands inside this ONE band, both gates pass by
    construction -- the band sits inside the footer-gap window
    ``[strip_top - max_gap, strip_top - min_gap]``, and its width is
    ``max_spread - epsilon``, so the worst-case pairwise spread of
    in-band columns stays strictly under ``max_spread`` (the gate is a
    strict ``<``; ``epsilon`` keeps the two-columns-at-opposite-edges
    case from landing exactly ON the threshold).

    Per column, ``hint`` is one of:

      * ``"keep"`` -- the bottom is already inside the shared band.
        NOTE: deliberately NOT ``|delta| <= max_spread``: two columns at
        opposite edges of a ±max_spread tolerance would both read
        "keep" while their pairwise spread is 2x the gate.
      * ``"grow ~N px [safe +lo..+hi]"`` / ``"trim ~N px [safe ...]"``
        -- the point estimate targets the band centre; the safe range
        is the full signed-delta interval into the band, integer-
        rounded INWARD (never widened past the true band).

    Pure function so the rule is unit-testable without Chromium.
    """
    center = strip_top - (min_gap + max_gap) / 2.0
    half = max(0.0, (max_spread - epsilon) / 2.0)
    band_lo = max(center - half, strip_top - max_gap)
    band_hi = min(center + half, strip_top - min_gap)
    if band_lo > band_hi:  # degenerate flags (e.g. min_gap > max_gap)
        band_lo = band_hi = center

    out: list[tuple[str, float, str]] = []
    for name, b in bottoms:
        if band_lo <= b <= band_hi:
            out.append((name, b, "keep"))
            continue
        delta = center - b  # +ve grow, -ve trim
        d_lo = math.ceil(band_lo - b)   # inward rounding:
        d_hi = math.floor(band_hi - b)  # never overpromise the band
        verb = "grow" if delta > 0 else "trim"
        if d_lo > d_hi:
            # No whole-pixel delta lands inside the band (band narrower
            # than 1 px after inward rounding). Do NOT call anything
            # "safe" here -- give the fractional target instead, with
            # the fewest decimals whose DISPLAYED value still lands
            # in-band (a legal --max-spread 0.5 collapses the band to
            # a point, where two decimals can miss; six decimals leave
            # a <=5e-7 px residual, not actionable in CSS anyway).
            for prec in (2, 3, 4, 5, 6):
                if band_lo <= b + round(delta, prec) <= band_hi:
                    break
            out.append((
                name, b,
                f"{verb} ~{int(round(abs(delta)))} px "
                f"(no whole-px safe delta; aim {delta:+.{prec}f} px)",
            ))
            continue
        out.append((
            name, b,
            f"{verb} ~{int(round(abs(delta)))} px "
            f"[safe {d_lo:+d}..{d_hi:+d}]",
        ))
    return (band_lo, band_hi), out


def format_band(lo: float, hi: float) -> str:
    """Display the band rounded INWARD (lower edge up, upper edge
    down): after snapping edges within 2 ULP of a display grid point
    onto it, the printed range is never wider than the true one. Two
    decimals for normal bands, six for the sub-0.05px bands a tiny
    --max-spread can produce. A band narrower than 1e-6 px collapses
    to its centre (a <=5e-7 px approximation -- the only case where
    the display is not strictly inside the band)."""
    bp = 2 if (hi - lo) >= 0.05 else 6
    scale = 10.0 ** bp

    def _snap(scaled: float) -> float:
        # An on-grid edge can scale to just above its integer
        # (2500.01 * 100 = 250001.00000000003) and get needlessly
        # ceil'd a whole step inward -- snap near-integer products.
        nearest = round(scaled)
        if abs(scaled - nearest) <= 2 * math.ulp(scaled):
            return float(nearest)
        return scaled

    disp_lo = math.ceil(_snap(lo * scale)) / scale
    disp_hi = math.floor(_snap(hi * scale)) / scale
    if disp_lo > disp_hi:  # inward rounding inverted a hairline band
        disp_lo = disp_hi = round((lo + hi) / 2, 6)
    return f"{disp_lo:.{bp}f}..{disp_hi:.{bp}f}"


def source_card_lines(html_text: str) -> list[int]:
    """Source line number of each ``data-measure-role="card"`` opening
    tag, in source order (== DOM order for static poster HTML).

    Reuses preflight's stack-based role scanner. Returns ``[]`` when the
    HTML can't be parsed -- callers must then omit line numbers rather
    than print wrong ones.
    """
    from .preflight import _RoleNestingChecker
    try:
        parser = _RoleNestingChecker()
        parser.feed(html_text)
    except Exception:
        return []
    return [ln for role, _p, ln, _t in parser.roles if role == "card"]


def format_edit_targets(
    columns: list[dict[str, Any]],
    card_lines: list[int],
    total_dom_cards: int,
    *,
    bottom_tol: float = 0.5,
) -> list[str]:
    """Human lines for the edit-targets block (pure, unit-testable).

    ``columns``: one dict per column --
      ``{"name", "hint", "cards": [{"card_idx", "x", "y", "bottom",
      "h", "anchor"}, ...]}`` (cards in any order; sorted here).
    ``card_lines``: source line per DOM card ordinal; used only when its
    length matches ``total_dom_cards`` (otherwise the mapping is not
    trustworthy and line numbers are omitted).
    Cards whose bottom ties the column bottom (within ``bottom_tol``)
    are ALL marked -- several cards can define the bottom jointly.
    """
    have_lines = len(card_lines) == total_dom_cards and total_dom_cards > 0
    out: list[str] = []
    out.append(
        "[measure] edit targets -- cards per column, top-to-bottom."
    )
    out.append(
        "  Locate by source line (L<n>) or by grepping the quoted anchor;"
    )
    out.append(
        "  do NOT re-read the whole file. Anchors are section-title text"
    )
    out.append(
        "  with math stripped -- confirm uniqueness before editing."
    )
    for col in columns:
        hint = col.get("hint") or ""
        out.append(f"  {col['name']}" + (f" ({hint}):" if hint else ":"))
        cards = sorted(
            col.get("cards", []), key=lambda c: (c["y"], c["x"])
        )
        col_bottom = max((c["bottom"] for c in cards), default=None)
        for c in cards:
            line = (
                f"L{card_lines[c['card_idx']]}"
                if have_lines and 0 <= c["card_idx"] < len(card_lines)
                else "L?"
            )
            mark = (
                "   <- bottom card (sets the column bottom)"
                if col_bottom is not None
                and abs(c["bottom"] - col_bottom) <= bottom_tol
                else ""
            )
            anchor = ascii_safe(c.get("anchor") or "")
            out.append(
                f"    card#{c['card_idx']:<3d} {line:<7s} "
                f"h={c['h']:6.0f}px  \"{anchor}\"{mark}"
            )
    return out


def group_layout(
    data: list[dict[str, Any]],
) -> tuple[
    dict[int, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Group raw ``[data-measure-role]`` boxes into the layout model.

    Returns ``(columns, heros, footer_strips, footers)``. ``columns`` is
    ``{index: {"box", "cards", "last_card_bottom"}}`` with cards
    attached to the column whose x-range contains the card's horizontal
    midpoint. Shared by ``measure`` and ``pack`` so both read the same
    geometry the same way.
    """
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
        for _ci, col in columns.items():
            if x_overlaps(el, col["box"]):
                col.setdefault("cards", []).append(el)
                prev = col["last_card_bottom"]
                if prev is None or el["bottom"] > prev:
                    col["last_card_bottom"] = el["bottom"]
                break

    return columns, heros, footer_strips, footers


def pick_strip(
    footer_strips: list[dict[str, Any]],
    footers: list[dict[str, Any]],
    target: float,
) -> tuple[dict[str, Any] | None, str | None]:
    """The strip the footer-gap gate anchors on: the footer-strip (or,
    failing that, footer) whose top sits nearest ``target``."""
    def _pick_nearest(strips: list[dict[str, Any]],
                      tgt: float) -> dict[str, Any] | None:
        if not strips:
            return None
        return min(strips, key=lambda s: abs(s["y"] - tgt))

    if footer_strips:
        return _pick_nearest(footer_strips, target), "footer-strip"
    if footers:
        return _pick_nearest(footers, target), "footer"
    return None, None


def cmd_measure(args: argparse.Namespace) -> int:
    """Budget-aware wrapper: the geometry gate lives in
    ``_measure_once``; this adds the consecutive-failure circuit
    breaker (see ``_posterly.budget``)."""
    html_path = Path(args.html).resolve()
    if not html_path.exists():
        _eprint(f"ERROR: HTML not found: {ascii_safe(html_path)}")
        return 2

    cap = int(
        getattr(args, "measure_budget", _budget.DEFAULT_MEASURE_BUDGET)
        or 0
    )
    bpath = _budget.budget_path(html_path)
    if getattr(args, "reset_budget", False):
        # Honoured even with --measure-budget 0: deleting the state is
        # exactly what the flag asks for. A FAILED removal (after the
        # zero-write fallback also failed) must not let the stale count
        # fire a phantom pre-render breaker right after we claimed a
        # fresh start -- disable the budget for this run.
        warn = _budget.clear(bpath, html_path.name)
        if warn is None:
            print("[measure] budget reset (--reset-budget)")
        else:
            _eprint(f"[measure] budget-state warning: {warn} -- "
                    "circuit breaker DISABLED for this run")
            cap = 0
    if cap > 0:
        count, warn = _budget.load_count(bpath, html_path.name)
        if warn:
            _eprint(f"[measure] budget-state warning: {warn}")
        if count >= cap:
            _eprint(_budget.breaker_banner(count, cap, pre_render=True))
            return _budget.EXIT_BUDGET_EXHAUSTED

    rc, measured = _measure_once(args, html_path)

    if cap > 0:
        if rc == 0:
            warn = _budget.clear(bpath, html_path.name)
            if warn:
                _eprint(
                    f"[measure] budget-state warning: {warn} -- a "
                    "later run may inherit this stale count; remove "
                    f"{bpath.name} by hand or pass --reset-budget"
                )
        elif rc == 1 and measured:
            count, warn = _budget.load_count(bpath, html_path.name)
            count += 1
            warn2 = _budget.record_failure(bpath, html_path.name, count)
            for w in (warn, warn2):
                if w:
                    _eprint(f"[measure] budget-state warning: {w}")
            print(
                f"[measure] consecutive failed measurements: "
                f"{count}/{cap} (resets on PASS or --reset-budget)"
            )
            if count >= cap:
                _eprint(_budget.breaker_banner(count, cap))
                return _budget.EXIT_BUDGET_EXHAUSTED
    return rc


def _measure_once(
    args: argparse.Namespace, html_path: Path
) -> tuple[int, bool]:
    """One render + gate evaluation.

    Returns ``(rc, measured)``. ``measured`` is True only when the page
    produced geometry (the JS probe ran) -- the budget wrapper counts
    only those failures; environment/navigation problems are not loop
    iterations.
    """
    try:
        from playwright.sync_api import sync_playwright
        from playwright.sync_api import TimeoutError as PWTimeoutError
    except ImportError:
        _eprint("ERROR: playwright not installed. Run:")
        _eprint("  python -m pip install playwright")
        _eprint("  python -m playwright install chromium")
        return 2, False

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
        return 2, False
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
            return 1, False
        if nav_timed_out:
            browser.close()
            _eprint(
                "FAIL: page did not reach network-idle within "
                f"{args.mathjax_timeout_ms} ms; refusing to measure a "
                "partially loaded poster. A blocked/slow remote resource "
                "(CDN image, web font, MathJax) is the usual cause -- "
                "inline assets, or raise --mathjax-timeout-ms."
            )
            return 1, False

        data = page.evaluate(_MEASURE_JS)
        # Optional merged polish pass on the SAME rendered page -- one
        # Chromium launch per loop round instead of two. Advisory only:
        # it prints before the measure verdict below and never touches
        # this gate's exit code; the loop's final soft gate remains a
        # standalone `polish --strict` run.
        if getattr(args, "with_polish", False):
            _polish.advisory_polish_on_page(page, html_path)
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
        return 1, True
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
        return 1, True
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
        return 1, True

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
        return 1, True

    columns, heros, footer_strips, footers = group_layout(data)

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
        return 1, True

    # Intra-column whitespace gate (HARD). The spread/gap gates only read
    # the LAST card's bottom -- `justify-content: space-between` (or a big
    # margin) pins the first card to the top and the last to the bottom,
    # so an under-filled column reads spread ~= 0 and a clean footer gap
    # while a void sits mid-column, plainly visible in print. (Observed
    # in the wild: 98-135 px voids against a 22.7 px design row-gap, with
    # polish's relative-threshold warn silent.) Gate: every gap between
    # consecutive stacked card rows must stay under --max-intercard-gap.
    # The same band has a floor: a gap under --min-intercard-gap buries
    # the card's drop shadow (`0 2u 6u` in the shipped templates) under
    # the next card, fusing the stack into one slab.
    max_icg = getattr(
        args, "max_intercard_gap", DEFAULT_MAX_INTERCARD_GAP
    )
    min_icg = getattr(
        args, "min_intercard_gap", DEFAULT_MIN_INTERCARD_GAP
    )
    icg_problems: list[str] = []
    icg_tight: list[str] = []
    icg_worst: tuple[str, float] | None = None
    icg_tightest: tuple[str, float] | None = None
    for ci, col in columns.items():
        gaps_c = intercard_gaps(col.get("cards", []))
        if not gaps_c:
            continue
        g = max(gaps_c)
        g_lo = min(gaps_c)
        if icg_worst is None or g > icg_worst[1]:
            icg_worst = (f"col{ci}", g)
        if icg_tightest is None or g_lo < icg_tightest[1]:
            icg_tightest = (f"col{ci}", g_lo)
        if g > max_icg:
            icg_problems.append(
                f"col{ci}: {g:.1f} px between stacked cards"
            )
        if g_lo < min_icg:
            icg_tight.append(
                f"col{ci}: {g_lo:.1f} px between stacked cards"
            )

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
        return 2, True

    bs = [b for _, b in bottoms]
    spread = max(bs) - min(bs)

    max_bottom = max(bs)

    next_strip, next_name = pick_strip(footer_strips, footers, max_bottom)

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
    if icg_worst is not None:
        print(f"  intercard gap in [{icg_tightest[1]:.2f} ({icg_tightest[0]}),"
              f" {icg_worst[1]:.2f} ({icg_worst[0]})] px"
              f"   (target [{min_icg}, {max_icg}])")
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
    if icg_problems:
        _eprint(
            "FAIL: intra-column whitespace void (max intercard gap "
            f"{max_icg:.0f} px):\n"
            + "\n".join("  " + p for p in icg_problems)
            + "\nColumns must be filled by CONTENT, not stretched "
            "whitespace. Do NOT use `justify-content: space-between` / "
            "`space-around` (or oversized margins) to fake bottom "
            "alignment -- it pins the last card to the bottom so spread "
            "reads ~0 while a void sits mid-column. Fix: grow figures or "
            "text, rebalance cards across columns, or use a fixed "
            "row-gap, then re-measure."
        )
        ok = False
    if icg_tight:
        _eprint(
            "FAIL: stacked cards too tight (min intercard gap "
            f"{min_icg:.0f} px):\n"
            + "\n".join("  " + p for p in icg_tight)
            + "\nA gap this small buries the card's drop shadow under "
            "the next card, fusing the stack into one slab. Fix: restore "
            "the column's design row-gap (shipped templates use 6u "
            "~= 22.7 px) and absorb the height elsewhere (trim content "
            "or shrink a figure); for a deliberately shadowless theme, "
            "lower --min-intercard-gap."
        )
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
        return 0, True

    # Failure path: surface per-column adjustment hints so the next
    # iteration is a directed edit, not a guess. The math is mechanical
    # (shared passing band inside the gap window; signed delta per
    # column), but readers reliably mis-derive it under time pressure --
    # a fixed gate failure was costing roughly an extra rebuild per
    # loop. Only print when the geometry is sane enough to give a
    # meaningful target: we need a footer-strip/footer (the anchor) and
    # at least one column bottom. Skip when the only failure is
    # `spread`-without-strip; the raw column dump above is already
    # actionable in that case.
    adjustments: list[tuple[str, float, str]] = []
    if next_strip is not None and bottoms:
        (band_lo, band_hi), adjustments = compute_adjustment_hints(
            bottoms,
            next_strip["y"],
            min_gap=args.min_gap,
            max_gap=args.max_gap,
            max_spread=args.max_spread,
        )

        print()
        print("[measure] suggested adjustments:")
        print(
            f"  shared passing band: {format_band(band_lo, band_hi)} px "
            "(EVERY column bottom must land in"
        )
        print(
            "  this one band; then gap and spread both pass. Anchor: "
            f"{next_name} top {next_strip['y']:.0f} px)"
        )
        for name, b, hint in adjustments:
            print(f"  {name:6s}  {b:8.2f} px -> {hint}")
        # The px magnitudes below are heuristics at typical print scale
        # (~3000 px canvas) and don't scale with the canvas -- they are
        # approximate by design; the per-column deltas above are exact.
        print(
            "  Tip: a body paragraph adds/removes ~25 px per wrapped line,"
            " a callout ~60-90 px,"
        )
        print(
            "       a small figure ~80-150 px. Prefer trimming the tallest"
            " column first."
        )

    # Edit-targets block: only for the fill/alignment failures where
    # "which card do I edit" is the next question (spread / footer gap /
    # intercard). Canvas-scale, position, and clip failures get their
    # own targeted messages above -- card targets would misdirect the
    # fix toward content. Printed even without a footer anchor (a
    # spread-only failure still needs a card to grow/trim).
    fill_failure = (
        spread >= args.max_spread
        or bool(icg_problems)
        or bool(icg_tight)
        or (
            next_strip is not None and gap_range is not None
            and (gap_range[0] < args.min_gap or gap_range[1] > args.max_gap)
        )
    )
    if fill_failure:
        try:
            html_text = html_path.read_text(
                encoding="utf-8", errors="replace"
            )
            card_lines = source_card_lines(html_text)
        except OSError:
            card_lines = []
        total_dom_cards = sum(1 for el in data if el["role"] == "card")
        hint_by_name = {name: hint for name, _b, hint in adjustments}
        target_cols = []
        for ci, col in sorted(columns.items()):
            target_cols.append({
                "name": f"col{ci}",
                "hint": hint_by_name.get(f"col{ci}", ""),
                "cards": [
                    {
                        "card_idx": c.get("card_idx", -1),
                        "x": c["x"], "y": c["y"],
                        "bottom": c["bottom"], "h": c["h"],
                        "anchor": c.get("anchor", ""),
                    }
                    for c in col.get("cards", [])
                ],
            })
        print()
        for line in format_edit_targets(
            target_cols, card_lines, total_dom_cards
        ):
            print(line)

    _eprint("[measure] FAIL -- alignment gate not met")
    return 1, True
