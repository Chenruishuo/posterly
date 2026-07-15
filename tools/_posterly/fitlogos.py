"""Logo-zone packing ADVISOR -- ``poster_check.py fit-logos``.

Ported from ResearchStudio's paper2poster ``fit_logos.py`` after a
cross-review of the two same-origin skills, re-shaped for posterly's
human-in-the-loop idiom: **read-only by design**. The original bakes
its arrangement straight into the HTML; here the browser is only used
to MEASURE the header's logo zone, and the tool PRINTS the arrangement
that maximises the one uniform height every institution mark shares --
rows, per-mark widths, fill -- plus a paste-ready proposal. The agent
applies it by hand only after judging it, or ignores it entirely.

The proposal is CLASS + CSS-RULE shaped (never inline ``style=`` --
that would trip style_check's hard Rule 2), keeps every mark inside a
``.logo-slot`` wrapper (so Gate E continues to see it), preserves the
original ``alt``, and carries ``data-color-exempt="logo"`` so a
brand-colored mark stays exempt from the color gate.

What the packer can and cannot judge: it equalizes BOUNDING BOXES. The
optical-weight judgment -- a dense institutional lockup reads smaller
than a clean wordmark in an equal box -- sits below any geometric
tool's resolution and stays with the author (SKILL.md, Logo handling).
Gate E stays the arbiter after any edit for ``<img>`` marks: the
proposal annotates when its uniform height would trip LOGO/QR-MISMATCH
and when a mark's width would trip LOGO/WIDE, so the agent can pick the
QR-matched height or a width-normalized ``logo-stack`` instead. One
caveat, stated in the snippet too: Gate E currently measures only
``.logo-slot img`` -- an inline ``<svg>`` logo is NOT gated and must be
verified by eye.

Pure geometry (``Mark`` / ``best_arrangement`` / ``render_snippet``) is
browser-free and unit-tested; ``cmd_fit_logos`` wires it to the same
print-emulated probe the other subcommands use.
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

from . import canvas as _canvas
from . import render as _render
from .textutil import ascii_safe

EXIT_USAGE = 2


def _eprint(*args: Any, **kw: Any) -> None:
    print(*args, file=sys.stderr, **kw)


# Mirrors the source tool: rows never grow past this without an explicit
# flag, vertical breathing between rows, horizontal gap between marks.
# The horizontal gap DEFAULT is the zone's own computed flex gap when
# the probe can read one; this constant is the fallback.
DEFAULT_MAX_ROWS = 3
ROW_GAP_FRAC = 0.14
DEFAULT_HGAP_PX = 24.0

# Gate E's QR-height contract (polish.py): a non-wide logo should sit
# within this fraction of the QR height. The advisor only ANNOTATES the
# conflict -- polish remains the gate.
QR_TOL = 0.15


@dataclass(frozen=True)
class Mark:
    """One institution mark: aspect ratio + opaque-ink weight."""
    src: str
    ar: float            # bounding-box aspect ratio w/h
    opaque: float = 1.0  # opaque-pixel fraction (tie-break weight)
    alt: str = ""        # preserved into the proposal markup


def measure_opaque(path: Path | None) -> float:
    """Opaque-pixel fraction of a raster's FULL canvas, for the fill
    tie-break (a sparse wordmark counts less than a solid seal). The
    full canvas -- not a trimmed bbox -- because the packing math sizes
    the mark by its natural AR, transparent padding included.
    Best-effort: PIL missing / unreadable / SVG -> 1.0."""
    if path is None:
        return 1.0
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return 1.0
    try:
        im = Image.open(path).convert("RGBA")
        w, h = im.size
        if w == 0 or h == 0:
            return 1.0
        opaque_px = sum(im.getchannel("A").histogram()[16:])
        return max(0.02, min(1.0, opaque_px / float(w * h)))
    except Exception:
        return 1.0


def _partitions(marks: list[Mark], max_rows: int):
    """Every unordered partition of ``marks`` into 1..max_rows rows."""
    n = len(marks)
    seen: set[frozenset] = set()
    for r in range(1, min(max_rows, n) + 1):
        for assign in product(range(r), repeat=n):
            if len(set(assign)) != r:
                continue
            rows = tuple(
                tuple(sorted(i for i in range(n) if assign[i] == j))
                for j in range(r)
            )
            key = frozenset(rows)
            if key in seen:
                continue
            seen.add(key)
            yield [[marks[i] for i in row] for row in rows]


def best_arrangement(
    marks: list[Mark],
    zone_w: float,
    zone_h: float,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    gap_frac: float = ROW_GAP_FRAC,
    hgap: float = DEFAULT_HGAP_PX,
) -> dict:
    """The row partition that MAXIMISES the one uniform mark height.

    For a partition into ``r`` rows, a uniform height ``h`` makes each
    row span ``h * sum(ar)`` plus the inter-mark gaps; the widest row
    caps ``h`` at ``(W - gaps) / sum_ar`` and the stack caps it at
    ``H / (r * (1 + gap_frac))``. Balanced rows fall out of maximising
    ``h``; ties break on real opaque-pixel fill. Every row carries the
    SAME height -- marks enlarge together, never some big / some small.
    """
    W = max(1.0, zone_w)
    H = max(1.0, zone_h)
    if not (math.isfinite(hgap) and hgap >= 0):
        hgap = DEFAULT_HGAP_PX
    best: dict | None = None
    for rows in _partitions(marks, max_rows):
        r = len(rows)
        sumars = [sum(m.ar for m in row) for row in rows]
        if max(sumars) <= 0:
            continue
        # A row whose inter-mark gaps ALONE exceed the zone width is
        # infeasible -- skip the partition instead of clamping to a
        # 1px budget and emitting a guaranteed-overflow proposal.
        h_width = math.inf
        for row, sa in zip(rows, sumars):
            if sa <= 0:
                continue
            avail = W - (len(row) - 1) * hgap
            if avail <= 0:
                h_width = -1.0
                break
            h_width = min(h_width, avail / sa)
        if h_width <= 0 or not math.isfinite(h_width):
            continue
        h = min(h_width, H / (r * (1 + gap_frac)))
        fill = sum(
            m.opaque * (h * m.ar) * h for row in rows for m in row
        ) / float(W * H)
        if best is None or (h, fill) > (best["h"], best["fill"]):
            best = {"rows": rows, "h": h, "fill": fill}
    if best is None:
        best = {"rows": [], "h": 0.0, "fill": 0.0}
    best["row_heights"] = [best["h"]] * len(best["rows"])
    return best


def _len_css(px: float, u_px: float) -> str:
    """A CSS length for ``px`` -- in the template's ``var(--u)`` unit
    when the probe measured one (so the screen preview keeps scaling),
    else plain px. Always rounded DOWN in px terms so a width-bound
    proposal can never overshoot its zone."""
    if u_px > 0:
        n = int(px / u_px * 10) / 10  # truncate at 0.1u -- inward
        return f"calc({n:g} * var(--u))"
    return f"{int(px)}px"


def render_snippet(
    rows: list[list[Mark]],
    h: float,
    *,
    hgap: float = DEFAULT_HGAP_PX,
    u_px: float = 0.0,
    cls: str = "logo-pack",
) -> str:
    """Paste-ready proposal: markup (each mark stays in a ``.logo-slot``
    so Gate E keeps seeing it; ``alt`` preserved and escaped;
    ``data-color-exempt`` carried for brand-colored marks) PLUS the CSS
    rules that size it -- explicit column wrapper, explicit row flex +
    gap (so the layout matches the packing math even in a template
    without ``.logo-row`` CSS). No inline ``style=`` anywhere --
    style_check Rule 2 hard-bans it. ``cls`` disambiguates the rules
    when a poster has several packed zones."""
    import html as _html

    row_gap = max(8.0, h * ROW_GAP_FRAC)
    lines: list[str] = ["<!-- markup: replace the zone's inner content -->"]
    lines.append(f'<div class="{cls}">')
    for row in rows:
        lines.append('  <div class="logo-row">')
        for m in row:
            if m.src == "(inline svg)":
                lines.append(
                    "    <!-- inline <svg> logo: keep it in its "
                    ".logo-slot; the CSS rule below sizes it. NOTE: "
                    "Gate E currently measures only <img> logos -- "
                    "verify an inline-SVG mark by eye -->"
                )
            else:
                src = _html.escape(m.src, quote=True)
                alt = _html.escape(m.alt or "", quote=True)
                lines.append(
                    f'    <div class="logo-slot"><img src="{src}" '
                    f'alt="{alt}" data-color-exempt="logo"></div>'
                )
        lines.append("  </div>")
    lines.append("</div>")
    lines.append("<!-- CSS: add to the poster stylesheet -->")
    lines.append(
        f".{cls} {{ display: flex; flex-direction: column; "
        f"align-items: center; gap: {_len_css(row_gap, u_px)}; }}"
    )
    lines.append(
        f".{cls} .logo-row {{ display: flex; align-items: center; "
        f"justify-content: center; gap: {_len_css(hgap, u_px)}; }}"
    )
    lines.append(
        f".{cls} .logo-slot img, .{cls} .logo-slot svg "
        f"{{ height: {_len_css(h, u_px)}; width: auto; "
        f"max-width: none; }}"
    )
    return "\n".join(lines)


_ZONES_JS = r"""
({extraSel, badSrcs}) => {
  const badSet = new Set(badSrcs || []);
  const out = {zones: [], qr_h: 0, header_w: 0, u: 0, badSelector: false};
  const header = document.querySelector(
    '[data-measure-role="header"], .header');
  if (header) out.header_w = header.getBoundingClientRect().width;
  // The template's --u unit in PIXELS so the proposal can be emitted
  // in var(--u) terms and keep scaling in the screen preview. Custom
  // properties compute to their raw token ("1mm" stays "1mm"), so a
  // parseFloat would misread unit'd values -- measure a probe element
  // sized `width: var(--u)` instead and read its pixel width.
  const uHost = document.querySelector('[data-measure-role="poster"], .poster')
             || document.documentElement;
  try {
    const probe = document.createElement('div');
    probe.style.cssText =
      'position:absolute;visibility:hidden;height:0;width:var(--u, 0px);';
    uHost.appendChild(probe);
    out.u = probe.getBoundingClientRect().width || 0;
    probe.remove();
  } catch (e) { out.u = 0; }
  // Gate E's QR contract only covers the header QR -- scope the probe
  // the same way so a footer/card QR can't trigger a bogus note.
  const qr = document.querySelector(
    '[data-measure-role="header"] .qr-block img, .header .qr-block img,' +
    '[data-measure-role="header"] .qr-block svg, .header .qr-block svg');
  if (qr) out.qr_h = qr.getBoundingClientRect().height;
  const zoneEls = [];
  const push = (el) => { if (!zoneEls.includes(el)) zoneEls.push(el); };
  // An APPLIED proposal nests fresh `.logo-row`s (and `.logo-slot`s)
  // inside its `.logo-pack` wrapper. The generic fallbacks below must
  // never pick those up: they'd shadow the real (stamped) outer zone
  // on a re-run and propose against the collapsed inner rows.
  const isPackCls = (n) => [...n.classList].some(
    c => c === 'logo-pack' || c.startsWith('logo-pack-'));
  const insidePack = (el) => {
    for (let n = el.parentElement; n; n = n.parentElement) {
      if (isPackCls(n)) return true;
    }
    return false;
  };
  if (extraSel) {
    // Explicit --zone: use ONLY this selector. No automatic discovery
    // runs beside or after it -- an invalid selector errors out, and
    // ZERO matches is reported by the CLI, never silently replaced by
    // an auto-discovered zone the user didn't name.
    try {
      document.querySelectorAll(extraSel).forEach(push);
    } catch (e) {
      out.badSelector = true;
      return out;
    }
    out.explicitZone = true;
  } else {
    document.querySelectorAll('[data-logo-zone]').forEach(push);
    if (!zoneEls.length) {
      // Auto mode: UNION of all three sources -- stamped zones
      // (data-lf-h0, an applied proposal's re-run marker), pack-external
      // `.logo-row`s, and pack-external `.logo-slot`s. A union, not
      // tiers: a poster with one applied+stamped zone and one untouched
      // row OR standalone slot must return both.
      const srcRank = new Map();   // el -> 0 stamp | 1 row | 2 slot
      const pushR = (el, r) => {
        push(el);
        const cur = srcRank.get(el);
        if (cur === undefined || r < cur) srcRank.set(el, r);
      };
      document.querySelectorAll('[data-lf-h0]')
        .forEach(el => pushR(el, 0));
      document.querySelectorAll(
        '.header .logo-row, [data-measure-role="header"] .logo-row'
      ).forEach(el => { if (!insidePack(el)) pushR(el, 1); });
      document.querySelectorAll(
        '.header .logo-slot, [data-measure-role="header"] .logo-slot'
      ).forEach(el => { if (!insidePack(el)) pushR(el, 2); });
      // Overlap resolution, PRIORITY-aware and GREEDY: order candidates
      // stamp > row > slot (outer first on rank ties), then keep each
      // one unless it overlaps an already-KEPT winner. Greedy, not
      // pairwise-simultaneous: a row eliminated by the stamped div
      // inside one of its branches must NOT drag down a disjoint
      // sibling slot in another branch -- a stamped inner div beats
      // the fallback row around it (or the row's stamp would be
      // bypassed all over again), while equal-rank nesting keeps the
      // outer (a slot inside its own row is the row's content, not a
      // second zone).
      // Total order (Array.sort contract): rank, then first-discovery
      // index. Each source pushes in document order and sources push
      // rank-ascending, so within a rank the index IS document order --
      // and a same-rank ancestor always precedes its descendant in
      // document order, giving outer-first on ties without a
      // non-transitive contains() comparator.
      const rank = (el) => srcRank.get(el);
      const ord = new Map(zoneEls.map((el, i) => [el, i]));
      const ordered = [...zoneEls].sort((a, b) =>
        rank(a) - rank(b) || ord.get(a) - ord.get(b));
      const kept = new Set();
      for (const el of ordered) {
        if (![...kept].some(k => k.contains(el) || el.contains(k))) {
          kept.add(el);
        }
      }
      const finalEls = zoneEls.filter(el => kept.has(el));
      zoneEls.length = 0;
      finalEls.forEach(el => zoneEls.push(el));
    }
  }
  // Every src still in the DOM -- lets the CLI report a broken image
  // that an onerror handler already REMOVED (it belongs to no zone).
  out.allSrcs = [...document.images]
    .map(im => im.getAttribute('src') || '').filter(s => s);
  zoneEls.forEach(z => {
    const r = z.getBoundingClientRect();
    // Re-run idempotency: once a proposal is APPLIED, a content-sized
    // zone collapses to the packed height, so a re-run would only ever
    // pack into the shrunken strip. The agent stamps the zone's
    // pre-application height as data-lf-h0 when applying (this tool is
    // read-only and never writes it). Trust max(stamp, live): the live
    // box wins when the TEMPLATE grew the zone; the stamp wins after a
    // collapse -- and a stale stamp from an older layout self-heals.
    const h0 = parseFloat(z.getAttribute('data-lf-h0') || '');
    const hasStamp = isFinite(h0) && h0 > 0;
    const H = hasStamp ? Math.max(r.height, h0) : r.height;
    if (r.width < 8 || H < 8) return;
    const cs = window.getComputedStyle(z);
    const gap = parseFloat(cs.columnGap || cs.gap || '') || 0;
    const items = [];
    const broken = [];
    z.querySelectorAll('img, svg').forEach(el => {
      if (el.closest('.qr-block')) return;
      if (el.parentElement && el.parentElement.closest('svg')) return;
      const isImg = el.tagName === 'IMG';
      const src = isImg ? (el.getAttribute('src') || '') : '(inline svg)';
      if (isImg && (!src || src.includes('{{'))) return;
      const b = el.getBoundingClientRect();
      const nw = isImg ? (el.naturalWidth || 0) : 0;
      const nh = isImg ? (el.naturalHeight || 0) : 0;
      const p0 = src.split('?')[0].split('#')[0];
      const looksSvg = /\.svgz?$/i.test(p0)
                    || /^data:image\/svg/i.test(src);
      // Broken marks never enter the packing: (1) the decode()/onerror
      // probe (authoritative -- catches a dead SVG rendering an
      // alt-text box), (2) zero natural size on a raster, (3) a
      // zero-size box on anything, inline <svg> included. The `why`
      // matters downstream: Gate E backstops broken RASTERS only.
      if (isImg && badSet.has(src)) {
        broken.push({src, why: looksSvg
          ? 'broken SVG file (failed to decode; NOT backstopped by ' +
            'Gate E -- fix it before packing)'
          : 'broken raster (failed to decode; polish also flags it ' +
            'as LOGO/BROKEN)'});
        return;
      }
      if (isImg && (nw <= 0 || nh <= 0) && !looksSvg) {
        broken.push({src, why: 'broken raster (zero natural size; ' +
          'polish also flags it as LOGO/BROKEN)'});
        return;
      }
      if (b.width < 2 || b.height < 2) {
        broken.push({src, why: isImg
          ? 'zero-size <img> box (renders nothing)'
          : 'zero-size inline <svg> (invisible, and NOT measured by ' +
            'Gate E)'});
        return;
      }
      const alt = isImg ? (el.getAttribute('alt') || '') : '';
      const ar = (nw > 0 && nh > 0) ? nw / nh
               : (b.height > 0 ? b.width / b.height : 1.0);
      items.push({src, alt, w: b.width, h: b.height, ar});
    });
    if (!items.length && !broken.length) return;
    out.zones.push({
      label: (z.getAttribute('data-logo-zone') || z.className
              || z.tagName).toString(),
      w: r.width, h: H, hLive: r.height, h0: hasStamp ? h0 : 0,
      // Class-TOKEN match via classList (attribute-substring selectors
      // miss tab/newline-separated class values): exact `logo-pack` or
      // a per-zone `logo-pack-N`.
      hasPack: [...z.querySelectorAll('*')].some(el =>
        [...el.classList].some(c =>
          c === 'logo-pack' || c.startsWith('logo-pack-'))),
      gap, items, broken,
    });
  });
  return out;
}
"""


def cmd_fit_logos(args: argparse.Namespace) -> int:
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
    if args.max_rows < 1:
        _eprint("ERROR: --max-rows must be >= 1.")
        return EXIT_USAGE
    if args.hgap is not None and not (
            math.isfinite(args.hgap) and args.hgap >= 0):
        _eprint("ERROR: --hgap must be a finite, non-negative number.")
        return EXIT_USAGE
    if args.zone is not None and not args.zone.strip():
        # An empty selector would read falsy in the probe and silently
        # re-enter automatic discovery -- refuse it instead.
        _eprint("ERROR: --zone must be a non-empty CSS selector.")
        return EXIT_USAGE

    resolved = _canvas.resolve_canvas(
        html_path, args.canvas, label="[fit-logos]"
    )
    if resolved is None:
        _eprint(
            "ERROR: could not find `@page { size: <W> <H> }` in HTML "
            "and no --canvas given."
        )
        return EXIT_USAGE
    _dims, viewport = resolved

    with sync_playwright() as p:
        browser, _ctx, page = _render.open_print_emulated_page(p, viewport)
        try:
            page.goto(html_path.as_uri(), wait_until="networkidle",
                      timeout=args.mathjax_timeout_ms)
        except PWTimeoutError:
            browser.close()
            _eprint("ERROR: page did not reach network-idle; cannot "
                    "measure a partially loaded poster.")
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
            _eprint(f"FAIL: {fail}")
            return 1
        broken_srcs = _render.undecodable_img_srcs(page)
        data = page.evaluate(
            _ZONES_JS, {"extraSel": args.zone, "badSrcs": broken_srcs}
        )
        browser.close()

    if data.get("badSelector"):
        _eprint(f"ERROR: --zone {args.zone!r} is not a valid CSS "
                f"selector.")
        return EXIT_USAGE

    zones = data.get("zones", [])
    qr_h = float(data.get("qr_h", 0) or 0)
    header_w = float(data.get("header_w", 0) or 0)
    u_px = float(data.get("u", 0) or 0)
    print(f"[fit-logos] {ascii_safe(html_path.name)}")
    still_in_dom = set(data.get("allSrcs") or [])
    for gone in sorted(set(broken_srcs) - still_in_dom):
        print(
            f"  WARN: '{ascii_safe(gone)}' failed to load and was "
            f"REMOVED from the DOM before measurement (an onerror "
            f"handler?) -- it belongs to no zone below; fix the file "
            f"and re-run."
        )
    if not zones:
        if data.get("explicitZone"):
            print(
                f"  --zone {args.zone!r} matched no measurable logo zone "
                f"(no match, or none at least 8px) -- nothing to pack. An "
                f"explicit selector never falls back to automatic "
                f"discovery."
            )
            return 0
        print(
            "  no logo zone found (looked for [data-logo-zone], a "
            "data-lf-h0-stamped zone, .header .logo-row, .header "
            ".logo-slot -- rows/slots inside an applied logo-pack are "
            "excluded; or pass --zone) -- nothing to pack."
        )
        return 0

    # Stay in sync with Gate E's LOGO/WIDE cap for the width annotation.
    from .polish import DEFAULT_LOGO_MAX_WIDTH_RATIO as _LOGO_MAX_W

    for zi, z in enumerate(zones):
        for bad in z.get("broken", []):
            print(f"\n  WARN: excluded "
                  f"{ascii_safe(str(bad.get('why', 'broken logo')))}: "
                  f"'{ascii_safe(str(bad.get('src', '')))}'")
        marks = [
            Mark(
                src=str(it["src"]),
                ar=max(0.05, float(it["ar"])),
                opaque=measure_opaque(
                    (html_path.parent / str(it["src"])).resolve()
                    if str(it["src"]) not in ("", "(inline svg)")
                    and not str(it["src"]).startswith(("data:", "http"))
                    else None
                ),
                alt=str(it.get("alt", "")),
            )
            for it in z["items"]
        ]
        if not marks:
            continue
        cur_hs = [float(it["h"]) for it in z["items"]]
        hgap = args.hgap if args.hgap is not None else (
            float(z.get("gap", 0) or 0) or DEFAULT_HGAP_PX
        )
        best = best_arrangement(
            marks, float(z["w"]), float(z["h"]), max_rows=args.max_rows,
            hgap=hgap,
        )
        print(f"\n  zone '{ascii_safe(str(z['label']))[:40]}' "
              f"({z['w']:.0f}x{z['h']:.0f}px, mark gap {hgap:.0f}px): "
              f"{len(marks)} mark(s)")
        h_live = float(z.get("hLive", z["h"]) or z["h"])
        h0 = float(z.get("h0", 0) or 0)
        if h0 > 0 and float(z["h"]) > h_live + 0.5:
            print(f"    (zone height {z['h']:.0f}px taken from the "
                  f"data-lf-h0 stamp; the live box is {h_live:.0f}px -- "
                  f"a previously applied pack collapsed it)")
        elif z.get("hasPack") and h0 <= 0:
            print(
                "    WARN: this zone already contains an applied "
                "logo-pack proposal but carries no data-lf-h0 stamp -- "
                "the measured height is likely the COLLAPSED packed "
                "height, so this proposal can only shrink the marks. "
                "Stamp the zone's pre-application height "
                "(data-lf-h0=\"<px>\") or re-run against the "
                "pre-application version."
            )
        spread = (max(cur_hs) / min(cur_hs)) if min(cur_hs) > 0 else 0.0
        print(f"    current heights : "
              + ", ".join(f"{h:.0f}px" for h in cur_hs)
              + (f"  (max/min = {spread:.2f}x)" if len(cur_hs) > 1 else ""))
        if not best["rows"]:
            print("    no arrangement found (zero-AR marks, or the "
                  "inter-mark gap alone exceeds the zone width -- "
                  "check --hgap vs the zone size)")
            continue
        print(f"    proposal        : {len(best['rows'])} row(s) @ "
              f"uniform {best['h']:.0f}px "
              f"(opaque fill ~{best['fill'] * 100:.0f}%)")
        for row in best["rows"]:
            for m in row:
                print(f"      - {ascii_safe(m.src)[:60]:<60} "
                      f"(AR {m.ar:.2f}) -> "
                      f"{m.ar * best['h']:.0f} x {best['h']:.0f}px")
        if qr_h > 0 and abs(best["h"] - qr_h) / qr_h > QR_TOL:
            print(
                f"    NOTE: uniform {best['h']:.0f}px is "
                f">{QR_TOL * 100:.0f}% off the QR height ({qr_h:.0f}px) "
                f"-- applied as-is, Gate E fires LOGO/QR-MISMATCH. "
                f"Either cap the height near the QR, or use the "
                f"width-normalized `logo-row logo-stack` (exempt from "
                f"the QR match) for wide wordmarks."
            )
        if header_w > 0:
            for m in (m for row in best["rows"] for m in row):
                w_frac = (m.ar * best["h"]) / header_w
                if w_frac > _LOGO_MAX_W:
                    print(
                        f"    NOTE: '{ascii_safe(m.src)[:50]}' would "
                        f"render at {w_frac * 100:.0f}% of header width "
                        f"(> {_LOGO_MAX_W * 100:.0f}% LOGO/WIDE cap) -- "
                        f"cap the shared height, or move it to a "
                        f"width-normalized `logo-stack` (its own row "
                        f"would NOT shrink it: the uniform height only "
                        f"grows when a row empties)."
                    )
        cls = "logo-pack" if len(zones) == 1 else f"logo-pack-{zi + 1}"
        print("    proposal (markup + CSS -- no inline style):")
        snip = render_snippet(
            best["rows"], best["h"], hgap=hgap, u_px=u_px, cls=cls,
        )
        for line in snip.splitlines():
            print(f"      {line}")
        print(
            "    (re-add a `.logo-chip` wrapper for any transparent / "
            "edge-white mark on a colored ground -- the proposal is "
            "bare slots; drop data-color-exempt on monochrome marks)"
        )
        if h0 <= 0:
            print(
                f"    (when applying, also stamp "
                f"data-lf-h0=\"{z['h']:.0f}\" on the zone element: a "
                f"content-sized zone collapses to the packed height, "
                f"and the stamp lets a re-run pack against the "
                f"original space instead of the shrunken strip)"
            )
        elif float(z["h"]) > h0 + 0.5:
            # The zone outgrew its stamp (template change) -- packing
            # used the live height; a stale stamp would silently lose
            # it on the NEXT re-run after this proposal collapses the
            # zone again.
            print(
                f"    (when applying, UPDATE the stamp to "
                f"data-lf-h0=\"{z['h']:.0f}\" -- the zone has grown "
                f"past the recorded {h0:.0f}px, and a stale stamp "
                f"would lose the new height on the next re-run)"
            )

    print(
        "\n  ADVISOR ONLY -- nothing was modified. Before applying: judge "
        "the OPTICAL weight (a dense lockup reads smaller than a clean "
        "wordmark in an equal box -- prefer each mark's simplest form; "
        "see Logo handling in SKILL.md), apply by hand if it reads "
        "right, then re-run the gates."
    )
    return 0
