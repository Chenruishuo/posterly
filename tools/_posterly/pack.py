"""Column-feasibility pre-check (``pack``) -- ADVISORY, run once
before entering the Step 4 measure loop.

The measure loop's worst failure mode is a column that CANNOT be
brought into band by figure resizing alone: the agent oscillates on it
for many rounds before concluding the cards must be re-packed across
columns. ``pack`` detects that up front by *actually probing* the two
endpoints in the browser: it temporarily forces every eligible card
``<img>`` to the smallest / largest width the Gate A aspect-ratio bands
tolerate, reads the REAL resulting column bottoms (so flex, floats,
figure rows, and text reflow are all accounted for by the layout engine
itself, not a paper model), then restores the original styles.

Verdict per column, against the footer-gap window
``allowed = [strip_top - max_gap, strip_top - min_gap]``:

  * ``REPACK_RECOMMENDED`` -- even with every figure at its Gate A
    floor the column bottom stays below the window: figure resizing
    alone cannot fit it. Move a card out / trim text.
  * ``FIGURE_ONLY_UNDERFILL`` -- even with every figure at its Gate A
    ceiling the bottom stays above the window: figures alone cannot
    fill it; the residual needs content (or the card set re-packed).
  * ``OK`` -- the window is reachable within the probed endpoints.

Plus one cross-column check: after clamping each OK column's reachable
range to the window, the theoretical minimum spread
``max(lo_i) - min(hi_i)`` must stay under ``--max-spread``.

Honest limits (why this is advisory, NEVER a hard gate):

  * The endpoints are Gate A's WARN thresholds, not physical minima --
    "no feasible state found inside the polish warning bands", not
    "cannot fit".
  * Only the two endpoints are probed; the envelope between them is an
    interpolation. Text reflow makes column bottoms non-monotonic in
    figure width, so a state between the endpoints can (rarely) fall
    outside the envelope -- another reason verdicts stay advisory.
  * The probe clears each image's height/min/max constraints while
    forcing the width, so it measures feasibility with those
    constraints relaxed, not under the current CSS verbatim.
  * ``data-fig-layout="beside-text"`` figures are left untouched (they
    opted out of the AR bands) and broken/icon-sized images are
    skipped.
  * Hero panels are NOT modelled: their bottoms join measure's spread
    gate, but pack has no resize policy for a hero stage. When a hero
    is present the cross-column check is skipped and the report says so
    loudly (``UNSUPPORTED_HERO``) rather than silently ignoring it.
  * Enlarging figures can also hit the asset gate's per-figure /
    total-area caps (``asset_check.py``) -- the recommended-width band
    is not automatically the asset-feasible band.

Mechanism inspired by ResearchStudio paper2poster's ``pack`` pre-check;
the endpoint-probing implementation is posterly's own (see NOTICE.md).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import canvas as _canvas
from . import render as _render
from .measure import group_layout, pick_strip
from .textutil import ascii_safe

#: Gate A bands, (min_width_ratio, max_width_ratio) of the card's
#: border-box width, keyed by shape. Floors mirror polish's WARN
#: thresholds (FIG/WIDE 0.65, FIG/SQUARE 0.55, FIG/TALL-SMALL 0.36);
#: ceilings mirror the documented "aim for" band tops (SKILL Gate A:
#: wide 100%, square 75%, tall 60%). Overridable via the same-named
#: CLI flags polish uses for its floors.
AR_WIDE_MIN, AR_WIDE_MAX = 0.65, 1.00
AR_SQUARE_MIN, AR_SQUARE_MAX = 0.55, 0.75
AR_TALL_MIN, AR_TALL_MAX = 0.36, 0.60

EXIT_OK = 0
EXIT_STRICT_FAIL = 1
EXIT_USAGE = 2


def _eprint(*args: Any, **kw: Any) -> None:
    print(*args, file=sys.stderr, **kw)


# Phase 1 (probe): geometry snapshot + per-image metadata, no mutation.
# Phase 2 (endpoints): force widths -> snapshot -> restore, twice.
# One evaluate call per phase; image ordinals are positions in
# querySelectorAll('[data-measure-role="card"] img') document order,
# stable across the two calls because the DOM is not mutated between
# them (style attributes are restored before returning).
_PACK_JS = r"""
(cfg) => {
  const collect = () =>
    Array.from(document.querySelectorAll('[data-measure-role]')).map(n => {
      const r = n.getBoundingClientRect();
      return {
        role: n.getAttribute('data-measure-role') || '',
        tag:  n.tagName.toLowerCase(),
        cls:  n.className || '',
        x: r.left, y: r.top, w: r.width, h: r.height,
        bottom: r.bottom, right: r.right,
      };
    });
  const imgs = Array.from(
    document.querySelectorAll('[data-measure-role="card"] img'));
  if (cfg.probe) {
    const meta = imgs.map((img, i) => {
      const r = img.getBoundingClientRect();
      const card = img.closest('[data-measure-role="card"]');
      const cr = card ? card.getBoundingClientRect() : { width: 0 };
      return {
        i: i,
        src: img.getAttribute('src') || '',
        fig_layout: img.getAttribute('data-fig-layout') || '',
        rendered_w: r.width, rendered_h: r.height,
        card_w: cr.width,
        natural_w: img.naturalWidth || 0,
        natural_h: img.naturalHeight || 0,
      };
    });
    return { base: collect(), meta: meta };
  }
  const saved = imgs.map(im => im.getAttribute('style'));
  const apply = (widths) => {
    for (const [idx, w] of widths) {
      const im = imgs[idx];
      if (!im) continue;
      im.style.setProperty('width', w + 'px', 'important');
      im.style.setProperty('height', 'auto', 'important');
      im.style.setProperty('max-width', 'none', 'important');
      im.style.setProperty('max-height', 'none', 'important');
      im.style.setProperty('min-width', '0', 'important');
      im.style.setProperty('min-height', '0', 'important');
    }
  };
  const restore = () => imgs.forEach((im, i) => {
    if (saved[i] === null) im.removeAttribute('style');
    else im.setAttribute('style', saved[i]);
  });
  apply(cfg.lo);
  const lo = collect();
  restore();
  apply(cfg.hi);
  const hi = collect();
  restore();
  return { lo: lo, hi: hi };
}
"""


def band_for_ar(
    ar: float,
    *,
    wide_min: float = AR_WIDE_MIN,
    square_min: float = AR_SQUARE_MIN,
    tall_min: float = AR_TALL_MIN,
) -> tuple[float, float]:
    """(min_ratio, max_ratio) of card width for a figure of aspect
    ratio ``ar`` -- Gate A's shape classes."""
    if ar > 1.3:
        return wide_min, AR_WIDE_MAX
    if ar >= 0.8:
        return square_min, AR_SQUARE_MAX
    return tall_min, AR_TALL_MAX


def _looks_like_svg(src: str) -> bool:
    """Same heuristic polish uses for the FIG/BROKEN SVG exemption:
    a ``.svg`` path/URL (query/fragment tolerated) or an SVG data URI.
    An extensionless SVG URL is not recognised (known shared gap)."""
    s = src.split("#", 1)[0].split("?", 1)[0].strip().lower()
    return s.endswith(".svg") or src.strip().lower().startswith(
        "data:image/svg"
    )


def plan_endpoints(
    meta: list[dict[str, Any]],
    *,
    wide_min: float,
    square_min: float,
    tall_min: float,
) -> tuple[list[list[float]], list[list[float]], list[dict[str, Any]]]:
    """Decide per-image endpoint widths. Returns ``(lo, hi, skipped)``
    where lo/hi are ``[ordinal, width_px]`` pairs for the JS and
    ``skipped`` records images left untouched (with a reason)."""
    lo: list[list[float]] = []
    hi: list[list[float]] = []
    skipped: list[dict[str, Any]] = []
    for m in meta:
        # Classification reads the authored ``src`` only: srcset /
        # <picture> selection (currentSrc) is not modelled -- posterly
        # posters use plain <img src>.
        has_natural = m["natural_w"] > 0 and m["natural_h"] > 0
        reason = None
        if m["fig_layout"] == "beside-text":
            reason = "beside-text opt-out (left at authored size)"
        elif not has_natural and not _looks_like_svg(m.get("src", "")):
            # Before the icon check: a broken raster's default 16x16
            # placeholder box would otherwise read as "inline icon".
            # And only a recognised SVG may fall back to its rendered
            # AR below: a broken raster with CSS-forced dimensions also
            # reports zero natural size but a non-zero box, and probing
            # it would size a blank rectangle.
            reason = "broken image (zero natural size, not an SVG)"
        elif not has_natural and (
            m["rendered_w"] <= 0 or m["rendered_h"] <= 0
        ):
            # Recognised SVG (by elimination) with nothing rendered:
            # broken too -- and it must not read as "inline icon".
            reason = "broken image (SVG with a zero-size rendered box)"
        elif m["rendered_w"] < 50:
            reason = "inline icon (<50px)"
        elif m["card_w"] <= 0:
            reason = "card width unreadable"
        elif has_natural:
            ar = m["natural_w"] / m["natural_h"]
        else:
            # Recognised SVG with a real box (zero natural size is
            # normal for SVG): AR from the rendered box.
            ar = m["rendered_w"] / m["rendered_h"]
        if reason is not None:
            skipped.append({"src": m["src"], "reason": reason})
            continue
        b_lo, b_hi = band_for_ar(
            ar, wide_min=wide_min, square_min=square_min,
            tall_min=tall_min,
        )
        lo.append([m["i"], b_lo * m["card_w"]])
        hi.append([m["i"], b_hi * m["card_w"]])
    return lo, hi, skipped


def pack_verdicts(
    cols: list[tuple[str, float, float]],
    allowed: tuple[float, float],
    max_spread: float,
) -> tuple[list[dict[str, Any]], float | None]:
    """Pure verdict logic (unit-testable without Chromium).

    ``cols``: ``(name, reachable_lo_bottom, reachable_hi_bottom)`` per
    column. ``allowed``: the footer-gap bottom window. Returns
    ``(per_column_results, cross_bound)`` where ``cross_bound`` is the
    theoretical minimum spread across OK columns when it is
    infeasible (``>= max_spread``), else ``None``.
    """
    a_lo, a_hi = allowed
    results: list[dict[str, Any]] = []
    inter: list[tuple[float, float]] = []
    for name, r_lo, r_hi in cols:
        if r_lo > r_hi:
            r_lo, r_hi = r_hi, r_lo
        if r_lo > a_hi:
            results.append({
                "name": name, "verdict": "REPACK_RECOMMENDED",
                "detail": (
                    f"over-full by ~{r_lo - a_hi:.0f}px at the Gate A "
                    "floor endpoint -- no feasible state found in the "
                    "probed width bands; move a card out or trim text"
                ),
            })
        elif r_hi < a_lo:
            results.append({
                "name": name, "verdict": "FIGURE_ONLY_UNDERFILL",
                "detail": (
                    f"~{a_lo - r_hi:.0f}px short at the Gate A ceiling "
                    "endpoint -- the residual needs content "
                    "(paper-sourced text / an extra card), not figure "
                    "growth"
                ),
            })
        else:
            clamp = (max(r_lo, a_lo), min(r_hi, a_hi))
            inter.append(clamp)
            results.append({
                "name": name, "verdict": "OK",
                "detail": (
                    f"window reachable (bottoms {clamp[0]:.0f}.."
                    f"{clamp[1]:.0f}px within the probed endpoints)"
                ),
            })
    cross: float | None = None
    if len(inter) >= 2:
        bound = max(lo for lo, _ in inter) - min(hi for _, hi in inter)
        if bound >= max_spread:
            cross = bound
    return results, cross


def cmd_pack(args: argparse.Namespace) -> int:
    try:
        from playwright.sync_api import sync_playwright
        from playwright.sync_api import TimeoutError as PWTimeoutError
    except ImportError:
        _eprint("ERROR: playwright not installed. Run:")
        _eprint("  python -m pip install playwright")
        _eprint("  python -m playwright install chromium")
        return EXIT_USAGE

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        _eprint(f"ERROR: HTML not found: {ascii_safe(html_path)}")
        return EXIT_USAGE

    resolved = _canvas.resolve_canvas(html_path, args.canvas, label="[pack]")
    if resolved is None:
        _eprint(
            "ERROR: could not find `@page { size: <W> <H> }` in HTML "
            "and no --canvas given."
        )
        return EXIT_USAGE
    _canvas_dims, viewport = resolved

    with sync_playwright() as p:
        browser, _ctx, page = _render.open_print_emulated_page(p, viewport)
        try:
            page.goto(html_path.as_uri(), wait_until="networkidle",
                      timeout=args.mathjax_timeout_ms)
        except PWTimeoutError:
            browser.close()
            _eprint("ERROR: page did not reach network-idle; cannot "
                    "probe a partially loaded poster.")
            return EXIT_USAGE
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
            _eprint(f"ERROR: {fail}")
            return EXIT_USAGE

        probe = page.evaluate(_PACK_JS, {"probe": True})
        lo_widths, hi_widths, skipped = plan_endpoints(
            probe["meta"],
            wide_min=args.wide_min_ratio,
            square_min=args.square_min_ratio,
            tall_min=args.tall_min_ratio,
        )
        endpoints = page.evaluate(
            _PACK_JS, {"probe": False, "lo": lo_widths, "hi": hi_widths}
        )
        browser.close()

    base_cols, heros, _strips, _footers = group_layout(probe["base"])
    if not base_cols:
        _eprint("ERROR: no [data-measure-role=\"column\"] found.")
        return EXIT_USAGE

    def _bottoms_by_index(snapshot: list[dict[str, Any]]) -> dict[int, float]:
        cols, _h, _s, _f = group_layout(snapshot)
        return {
            ci: (col["last_card_bottom"]
                 if col["last_card_bottom"] is not None
                 else col["box"]["bottom"])
            for ci, col in cols.items()
        }

    lo_b = _bottoms_by_index(endpoints["lo"])
    hi_b = _bottoms_by_index(endpoints["hi"])

    # Anchor the target window on the LO-state strip, not the base
    # state: an over-full flex column PUSHES the strip down with it
    # (min-height:auto floors the column at its content), so the
    # base-state strip legitimizes exactly the overflow pack must
    # detect. With every figure at its floor the strip sits at its
    # least-pushed -- i.e. designed -- position (in the shipped grid
    # templates it doesn't move at all).
    lo_cols, _lh, lo_strips, lo_footers = group_layout(endpoints["lo"])
    lo_max_bottom = max(
        [b for b in lo_b.values()] or [0.0]
    )
    next_strip, next_name = pick_strip(lo_strips, lo_footers, lo_max_bottom)
    if next_strip is None:
        _eprint(
            "ERROR: no footer-strip/footer below content -- pack needs "
            "the footer-gap anchor to define the target window."
        )
        return EXIT_USAGE

    _vw, vh = viewport
    # The WHOLE below-columns block must fit, not just the anchor
    # strip: a footer under an in-canvas strip can be the element
    # pushed off the page (both landscape templates ship strip+footer).
    downstream_bottom = max(
        (el["bottom"] for el in lo_strips + lo_footers
         if el["bottom"] >= next_strip["y"]),
        default=next_strip["bottom"],
    )
    canvas_overflow = downstream_bottom > vh + 2.0

    allowed = (
        next_strip["y"] - args.max_gap,
        next_strip["y"] - args.min_gap,
    )
    cols_in = [
        (f"col{ci}", lo_b.get(ci, 0.0), hi_b.get(ci, 0.0))
        for ci in sorted(base_cols)
    ]
    if canvas_overflow:
        # Even at the figure floors the layout pushes the strip/footer
        # block past the canvas: the poster is over-full regardless of
        # any window arithmetic -- a GLOBAL non-OK state (never
        # "[pack] OK", and --strict fails). Attribute it to the columns
        # whose bottoms leave no room for the gap plus everything below
        # the strip (the strip itself and any footer under it).
        downstream = downstream_bottom - next_strip["y"]
        blamed = 0
        results = []
        for name, r_lo, r_hi in cols_in:
            over = (
                min(r_lo, r_hi) + args.min_gap + downstream > vh
            )
            blamed += bool(over)
            results.append({
                "name": name,
                "verdict": "REPACK_RECOMMENDED" if over else "OK",
                "detail": (
                    (f"bottom {min(r_lo, r_hi):.0f}px + gap + the "
                     f"{downstream:.0f}px strip/footer below cannot fit "
                     f"the {vh:.0f}px canvas even with figures at their "
                     "Gate A floors -- move a card out or cut text")
                    if over else
                    "column bottoms fit the canvas at figure floors"
                ),
            })
        if not blamed:
            print(
                "[pack] NOTE: no single column accounts for the "
                "overflow -- fixed content above/below the columns "
                "(header, banner, strip margins) is oversized for this "
                "canvas."
            )
        cross = None
    else:
        results, cross = pack_verdicts(cols_in, allowed, args.max_spread)
        if heros:
            # The hero's bottom joins measure's spread gate but pack
            # has no resize policy for it -- a cross-column bound
            # computed WITHOUT the hero would be misleading in every
            # consumer (stdout, JSON, --strict alike).
            cross = None

    print()
    if canvas_overflow:
        print(f"[pack] CANVAS OVERFLOW: the strip/footer block below "
              f"the columns extends to {downstream_bottom:.0f}px -- "
              f"past the {vh:.0f}px canvas even with every figure at "
              "its Gate A floor. Content below the canvas is LOST in "
              "print.")
    print(f"[pack] target window: column bottoms in "
          f"{allowed[0]:.0f}..{allowed[1]:.0f} px "
          f"({next_name} top {next_strip['y']:.0f} px at figure floors, "
          f"gap {args.min_gap:.0f}..{args.max_gap:.0f} px)")
    print("[pack] probed endpoints = Gate A width bands "
          "(floors are polish WARN thresholds, not physical minima)")
    for (name, r_lo, r_hi), res in zip(cols_in, results):
        print(f"  {name:6s}  probed envelope {min(r_lo, r_hi):8.0f}.."
              f"{max(r_lo, r_hi):8.0f} px -> {res['verdict']}")
        print(f"          {res['detail']}")
    for s in skipped:
        print(f"  (skipped {ascii_safe(s['src'])}: {s['reason']})")
    if heros:
        print(
            "[pack] UNSUPPORTED_HERO: a hero panel is present. Its "
            "bottom joins measure's spread gate but pack has no resize "
            "policy for a hero stage -- the cross-column check is "
            "SKIPPED; judge the hero/column balance in the measure loop."
        )
    elif cross is not None:
        print(
            f"[pack] CROSS-COLUMN: even inside the probed endpoints the "
            f"minimum possible spread is ~{cross:.0f}px "
            f">= --max-spread {args.max_spread:.0f}px -- no figure "
            "sizing makes these columns meet; re-pack cards across "
            "columns before entering the loop."
        )
    print(
        "[pack] advisory only; the envelope covers the two probed "
        "endpoints, not every width in between. Note: enlarging "
        "figures toward the ceiling can hit asset_check's area caps "
        "(if you use the asset gate) -- the width band is not "
        "automatically asset-feasible."
    )

    bad = [r for r in results if r["verdict"] != "OK"]
    infeasible = bool(bad) or cross is not None or canvas_overflow
    if not infeasible:
        print("[pack] OK -- every column can reach the window within "
              "the probed figure bands.")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({
                "allowed_bottom_window": list(allowed),
                "canvas_overflow": canvas_overflow,
                "columns": [
                    {**res, "probed_envelope": [min(lo, hi), max(lo, hi)]}
                    for (n, lo, hi), res in zip(cols_in, results)
                ],
                "cross_column_min_spread": cross,
                "hero_present": bool(heros),
                "skipped_images": skipped,
            }, indent=2),
            encoding="utf-8",
        )
        print(f"[pack] report -> {ascii_safe(args.json_out)}")

    if args.strict and infeasible:
        return EXIT_STRICT_FAIL
    return EXIT_OK
