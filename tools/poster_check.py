#!/usr/bin/env python3
"""poster_check — unified CLI for HTML academic posters.

Six subcommands:

  measure        Print-emulate HTML in headless Chromium, measure all
                 ``[data-measure-role]`` elements, report column-bottom
                 spread and gap to the next horizontal strip. The HARD
                 alignment gate (spread < 5 px is non-negotiable).
                 Carries the loop circuit breaker: consecutive failed
                 measurements are counted on disk; at the cap it exits
                 3 instead of measuring again (``--measure-budget`` /
                 ``--reset-budget``).
  pack           ADVISORY column-feasibility pre-check -- run ONCE
                 before entering the measure loop. Probes each card
                 figure at its Gate A width-band endpoints in the
                 browser and reports which columns cannot reach the
                 footer-gap window by figure resizing alone
                 (REPACK_RECOMMENDED / FIGURE_ONLY_UNDERFILL).
  fit-logos      ADVISORY logo-zone packer (read-only). Measures the
                 header's logo zone and prints the row arrangement
                 that maximises the one uniform mark height, plus a
                 paste-ready snippet. Never edits the file: the agent
                 judges the proposal (optical weight, Gate E) and
                 applies it by hand -- or not at all.
  preflight      Static HTML scan: LaTeX residue, raw '<' inside
                 ``$…$`` / ``$$…$$`` / ``\\(…\\)`` / ``\\[…\\]``,
                 missing local images, missing data-measure-role.
  polish         Visual-polish warnings on figure sizing, broken
                 images, typography orphans, and space-between fill.
                 Soft gate; warns by default. ``--strict`` to fail.
                 Hard-fails if there's no measurement markup at all.
  verify-final   Run ``pdfinfo`` on a rendered PDF; check page count,
                 dimensions match the expected canvas (``--canvas`` or
                 ``--from-html``), and file size under a limit.

All logic lives in the ``_posterly`` package next to this file. This
script is a thin argparse dispatcher.
"""
from __future__ import annotations

import argparse
import os
import sys

# Make `_posterly` importable when this file is run directly via
# `python tools/poster_check.py …`.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from _posterly import budget as _budget  # noqa: E402
from _posterly import canvas as _canvas  # noqa: E402
from _posterly import fitlogos as _fitlogos  # noqa: E402
from _posterly import measure as _measure  # noqa: E402
from _posterly import pack as _pack  # noqa: E402
from _posterly import polish as _polish  # noqa: E402
from _posterly import preflight as _preflight  # noqa: E402
from _posterly import verify_final as _verify_final  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="poster_check",
        description="Measure / pack / preflight / polish / verify a "
                    "poster HTML+PDF pair.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # --- measure --------------------------------------------------------
    pm = sub.add_parser(
        "measure",
        help="alignment + gap gate (print-emulated, HARD gate)",
    )
    pm.add_argument("html", help="path to poster.html")
    pm.add_argument(
        "--max-spread", type=float, default=5.0,
        help="hard gate: max column-bottom spread in px "
             "(default 5.0; aim < 3.0)",
    )
    pm.add_argument(
        "--min-gap", type=float, default=30.0,
        help="min gap to footer-strip/footer (default 30 px)",
    )
    pm.add_argument(
        "--max-gap", type=float, default=50.0,
        help="max gap to footer-strip/footer (default 50 px)",
    )
    pm.add_argument(
        "--canvas", type=_canvas.parse_canvas_arg, default=None,
        help="override canvas (e.g. '60x36in' or 'A0 portrait'); "
             "by default we parse @page from the HTML",
    )
    pm.add_argument(
        "--allow-empty-column", action="store_true",
        help="don't fail when a column has no cards "
             "(fallback to column.bottom; risky)",
    )
    pm.add_argument(
        "--allow-no-footer-gap", action="store_true",
        help="don't fail when neither footer-strip nor footer exists "
             "below the content",
    )
    pm.add_argument(
        "--settle-ms", type=int, default=500,
        help="extra wait after MathJax + fonts.ready settle "
             "(default 500)",
    )
    pm.add_argument(
        "--mathjax-timeout-ms", type=int, default=15000,
        help="hard timeout for MathJax typeset (default 15000); "
             "exceeding it FAILS the gate, not warns",
    )
    pm.add_argument(
        "--min-canvas-fill", type=float, default=0.95,
        help="hard gate: [data-measure-role='poster'] must fill at "
             "least this fraction of the print viewport in BOTH "
             "dimensions (default 0.95). Catches the silent 'forgot "
             "the print media-query unit override' bug where the "
             "poster renders at screen scale into a much bigger "
             "print page.",
    )
    pm.add_argument(
        "--max-canvas-fill", type=float, default=1.01,
        help="hard gate: poster must NOT exceed this fraction of the "
             "print viewport (default 1.01; i.e. <=1%% overshoot is "
             "tolerated for sub-pixel rounding). The symmetric of "
             "--min-canvas-fill catches the case where a hardcoded "
             "`width` in px exceeds `@page size`.",
    )
    pm.add_argument(
        "--position-tol-px", type=float, default=2.0,
        help="hard gate: poster's bbox edges must align with the print "
             "viewport's origin within this many px (default 2.0). "
             "Catches `transform: translate*`, mis-positioned absolute "
             "layout, and stray body margin in print.",
    )
    pm.add_argument(
        "--max-clip-px", type=float, default=2.0,
        help="hard gate: a card/column/hero whose content is clipped by "
             "overflow:hidden|clip|scroll|auto by MORE than this many px "
             "(scrollHeight-clientHeight) FAILS -- clipped content is "
             "silently lost in print while the box still looks aligned. "
             "Also the tolerance for the poster-root canvas-overflow gate "
             "(content spilling past the canvas), so raising it relaxes "
             "both (default 2.0; sub-pixel rounding tolerated).",
    )
    pm.add_argument(
        "--max-intercard-gap", type=float,
        default=_measure.DEFAULT_MAX_INTERCARD_GAP,
        help="hard gate: max whitespace between consecutive stacked "
             "cards in a column (default 50 px, same ceiling as the "
             "footer gap). Catches `justify-content: space-between` "
             "faking bottom alignment on an under-filled column -- "
             "spread reads ~0 while a void sits mid-column.",
    )
    pm.add_argument(
        "--min-intercard-gap", type=float,
        default=_measure.DEFAULT_MIN_INTERCARD_GAP,
        help="hard gate: min whitespace between consecutive stacked "
             "cards (default 12 px). Tighter gaps bury the card's drop "
             "shadow (templates ship `0 2u 6u`) under the next card, "
             "fusing the stack into one slab. Set 0 to disable for "
             "shadowless themes.",
    )
    pm.add_argument(
        "--with-polish", action="store_true",
        help="also run the visual-polish pass (figure sizing, orphans, "
             "space-between, header logos, ...) on the SAME rendered "
             "page -- one browser launch per loop round instead of two. "
             "ADVISORY: the polish report prints at default thresholds "
             "and never changes measure's exit code; the final soft "
             "gate remains a standalone `polish` run (--strict).",
    )
    pm.add_argument(
        "--json-out", default=None,
        help="dump raw measurement to JSON",
    )
    pm.add_argument(
        "--measure-budget", type=int,
        default=_budget.DEFAULT_MEASURE_BUDGET,
        help="circuit breaker: exit 3 after this many CONSECUTIVE "
             "failed measurements on this poster. The counter persists "
             "on disk next to the HTML, resets on the first PASS or "
             "after 12h idle. 0 disables. (default %(default)s)",
    )
    pm.add_argument(
        "--reset-budget", action="store_true",
        help="zero the on-disk failure counter before measuring (a "
             "deliberate fresh start, e.g. after a big re-pack). "
             "Honoured even with --measure-budget 0: the state file is "
             "cleared regardless of whether the breaker is enabled.",
    )
    pm.set_defaults(func=_measure.cmd_measure)

    # --- pack -------------------------------------------------------------
    pk = sub.add_parser(
        "pack",
        help="ADVISORY column-feasibility pre-check (run once BEFORE "
             "the measure loop)",
    )
    pk.add_argument("html", help="path to poster.html")
    pk.add_argument(
        "--canvas", type=_canvas.parse_canvas_arg, default=None,
        help="override canvas (default: parse @page from HTML)",
    )
    pk.add_argument(
        "--max-spread", type=float, default=5.0,
        help="spread threshold used for the cross-column feasibility "
             "bound (default 5.0; keep in sync with measure)",
    )
    pk.add_argument(
        "--min-gap", type=float, default=30.0,
        help="min gap to footer-strip/footer (default 30 px)",
    )
    pk.add_argument(
        "--max-gap", type=float, default=50.0,
        help="max gap to footer-strip/footer (default 50 px)",
    )
    pk.add_argument(
        "--wide-min-ratio", type=float, default=_pack.AR_WIDE_MIN,
        help="Gate A floor probed for wide figures (AR>1.3); keep in "
             "sync with polish (default %(default)s)",
    )
    pk.add_argument(
        "--square-min-ratio", type=float, default=_pack.AR_SQUARE_MIN,
        help="Gate A floor probed for square figures (0.8<=AR<=1.3); "
             "keep in sync with polish (default %(default)s)",
    )
    pk.add_argument(
        "--tall-min-ratio", type=float, default=_pack.AR_TALL_MIN,
        help="Gate A floor probed for tall figures (AR<0.8); keep in "
             "sync with polish (default %(default)s)",
    )
    pk.add_argument(
        "--settle-ms", type=int, default=500,
        help="extra wait after layout settles (default 500)",
    )
    pk.add_argument(
        "--mathjax-timeout-ms", type=int, default=15000,
        help="hard timeout for MathJax typeset (default 15000)",
    )
    pk.add_argument(
        "--strict", action="store_true",
        help="exit 1 when any column is REPACK_RECOMMENDED / "
             "FIGURE_ONLY_UNDERFILL or the cross-column bound trips "
             "(default: always exit 0 -- advisory)",
    )
    pk.add_argument(
        "--json-out", default=None,
        help="write the pack report as JSON",
    )
    pk.set_defaults(func=_pack.cmd_pack)

    # --- fit-logos ------------------------------------------------------
    fl = sub.add_parser(
        "fit-logos",
        help="ADVISORY logo-zone packer: print the max-uniform-height "
             "row arrangement for the header logos (read-only)",
    )
    fl.add_argument("html", help="path to poster.html")
    fl.add_argument(
        "--canvas", type=_canvas.parse_canvas_arg, default=None,
        help="override canvas (default: parse @page from HTML)",
    )
    fl.add_argument(
        "--zone", default=None,
        help="CSS selector for the logo zone(s). When given, ONLY this "
             "selector is used -- no automatic discovery, and zero "
             "matches is reported, never silently replaced. Default "
             "discovery: any [data-logo-zone]; else the UNION of "
             "data-lf-h0-stamped zones, .header .logo-row, and "
             "standalone .header .logo-slot (nested candidates resolve "
             "stamp > row > slot, outer wins ties) -- rows/slots INSIDE "
             "an applied logo-pack are never auto-discovered",
    )
    fl.add_argument(
        "--max-rows", type=int, default=_fitlogos.DEFAULT_MAX_ROWS,
        help="row-partition search cap (default %(default)s)",
    )
    fl.add_argument(
        "--hgap", type=float, default=None,
        help="horizontal gap between marks in a row, px at true canvas "
             "scale (default: the zone's own computed flex gap, else "
             f"{_fitlogos.DEFAULT_HGAP_PX:.0f})",
    )
    fl.add_argument(
        "--settle-ms", type=int, default=500,
        help="extra wait after layout settles (default 500)",
    )
    fl.add_argument(
        "--mathjax-timeout-ms", type=int, default=15000,
        help="hard timeout for MathJax typeset (default 15000)",
    )
    fl.set_defaults(func=_fitlogos.cmd_fit_logos)

    # --- preflight ------------------------------------------------------
    pp = sub.add_parser(
        "preflight",
        help="static HTML lint (LaTeX residue, math, images, roles)",
    )
    pp.add_argument("html", help="path to poster.html")
    pp.set_defaults(func=_preflight.cmd_preflight)

    # --- polish ---------------------------------------------------------
    ppl = sub.add_parser(
        "polish",
        help="visual-polish warnings (figure size, orphans, "
             "space-between, flex/<br>, header logos)",
    )
    ppl.add_argument("html", help="path to poster.html")
    ppl.add_argument(
        "--canvas", type=_canvas.parse_canvas_arg, default=None,
        help="override canvas (default: parse @page from HTML)",
    )
    ppl.add_argument(
        "--settle-ms", type=int, default=500,
        help="extra wait after layout settles (default 500)",
    )
    ppl.add_argument(
        "--mathjax-timeout-ms", type=int, default=15000,
        help="hard timeout for MathJax typeset (default 15000)",
    )
    ppl.add_argument(
        "--wide-min-ratio", type=float,
        default=_polish.DEFAULT_WIDE_MIN_RATIO,
        help="wide figures (AR>1.3) must occupy >= this fraction of "
             "card width (default %(default)s -- the defect FLOOR; a "
             "figure-dominant card reads best at 90-100%%)",
    )
    ppl.add_argument(
        "--tall-max-ratio", type=float,
        default=_polish.DEFAULT_TALL_MAX_RATIO,
        help="tall figures (AR<0.8) above this fraction trigger a "
             "text-right recommendation (default %(default)s)",
    )
    ppl.add_argument(
        "--tall-min-ratio", type=float,
        default=_polish.DEFAULT_TALL_MIN_RATIO,
        help="tall figures (AR<0.8) BELOW this fraction of card width "
             "trigger FIG/TALL-SMALL (small + wide side margins); enlarge "
             "or wrap text. Hard floor, not the ideal (aim 45-60%%) "
             "(default %(default)s)",
    )
    ppl.add_argument(
        "--square-min-ratio", type=float,
        default=_polish.DEFAULT_SQUARE_MIN_RATIO,
        help="square figures (0.8<=AR<=1.3) must occupy >= this "
             "fraction (default %(default)s)",
    )
    ppl.add_argument(
        "--hero-letterbox-fill", type=float,
        default=_polish.DEFAULT_HERO_LETTERBOX_FILL,
        help="HERO/STAGE-LETTERBOX: a hero figure filling BELOW this "
             "fraction of its hero-stage width (while the stage is much "
             "wider than the image AR, see --hero-letterbox-ar-mult) leaves "
             "big symmetric side voids (default %(default)s)",
    )
    ppl.add_argument(
        "--hero-letterbox-ar-mult", type=float,
        default=_polish.DEFAULT_HERO_LETTERBOX_AR_MULT,
        help="HERO/STAGE-LETTERBOX trips only when stage_AR / image_AR "
             "exceeds this -- i.e. the stage is this many times wider "
             "(relative to the image) than the image needs (default "
             "%(default)s); guards against flagging a genuine full-bleed "
             "hero where image AR ~= stage AR",
    )
    ppl.add_argument(
        "--beside-void-ratio", type=float,
        default=_polish.DEFAULT_BESIDE_VOID_RATIO,
        help="FIG/BESIDE-TEXT-VOID: a figure floated beside text whose "
             "text stops more than this fraction of the figure height "
             "short of its bottom leaves an L-shaped void (default "
             "%(default)s)",
    )
    ppl.add_argument(
        "--max-space-between-fill", type=float,
        default=_polish.DEFAULT_MAX_SPACE_BETWEEN_FILL,
        help="warn if a space-between column has an inter-card gap "
             "exceeding this fraction of column height "
             "(default %(default)s)",
    )
    ppl.add_argument(
        "--max-card-trailing", type=float,
        default=_polish.DEFAULT_MAX_CARD_TRAILING,
        help="warn (CARD/TRAILING) if a card leaves more than this "
             "fraction of its height blank below the last line "
             "(default %(default)s); catches a flex-stretched card "
             "padded with whitespace to fake a full page",
    )
    ppl.add_argument(
        "--max-card-inner-void", type=float,
        default=_polish.DEFAULT_CARD_INNER_VOID,
        help="warn (CARD/INNER-VOID) if a card's largest gap between two "
             "stacked children exceeds the stated row-gap by more than this "
             "fraction of card height (default %(default)s); catches a "
             "bottom-pinned tail (margin-top:auto / space-*) opening a void "
             "in the middle of a stretched equal-height card",
    )
    ppl.add_argument(
        "--min-card-inner-void-px", type=float,
        default=_polish.DEFAULT_CARD_INNER_VOID_PX,
        help="CARD/INNER-VOID absolute floor in px (default %(default)s); a "
             "gap must exceed BOTH this and --max-card-inner-void to flag, "
             "so a sub-line gap on a small card stays quiet. The same "
             "ratio+floor also drive TRACK/INNER-VOID on header/footer "
             "tracks (a vertical masthead spine or side rail)",
    )
    ppl.add_argument(
        "--min-contrast", type=float,
        default=_polish.DEFAULT_MIN_CONTRAST,
        help="warn (CONTRAST) if a rendered text run's WCAG ratio against "
             "the solid ground beneath it falls below this (default "
             "%(default)s -- flags only unambiguous defects; deliberate "
             "muted inks sit ~3.5+; values above 7.0 are not supported -- "
             "the collector only ships sub-7 samples). Text over "
             "images/gradients/translucency is skipped",
    )
    ppl.add_argument(
        "--min-unprotected-wraps", type=int,
        default=_polish.DEFAULT_MIN_UNPROTECTED_WRAPS,
        help="aggregate TEXT-WRAP note fires when at least this many "
             "wrapped text blocks carry neither text-wrap: pretty nor "
             "balance (default %(default)s) -- the dropped-base-defenses "
             "signature of a custom skeleton",
    )
    ppl.add_argument(
        "--logo-max-width-ratio", type=float,
        default=_polish.DEFAULT_LOGO_MAX_WIDTH_RATIO,
        help="warn (LOGO/WIDE) if a header logo renders wider than this "
             "fraction of the header width (default %(default)s)",
    )
    ppl.add_argument(
        "--logo-qr-tol", type=float,
        default=_polish.DEFAULT_LOGO_QR_TOL,
        help="warn (LOGO/QR-MISMATCH) if a non-wide header logo's height "
             "differs from the QR's by more than this fraction; logo-wide "
             "slots use a band instead (default %(default)s)",
    )
    ppl.add_argument(
        "--rightblock-max-ratio", type=float,
        default=_polish.DEFAULT_RIGHTBLOCK_MAX_RATIO,
        help="warn (HEADER/TITLE-SQUEEZED) if the header's right block "
             "exceeds this fraction of header width (default %(default)s)",
    )
    ppl.add_argument(
        "--title-min-ratio", type=float,
        default=_polish.DEFAULT_TITLE_MIN_RATIO,
        help="warn (HEADER/TITLE-SQUEEZED) if the title block falls below "
             "this fraction of header width (default %(default)s)",
    )
    ppl.add_argument(
        "--title-offset-max", type=float,
        default=_polish.DEFAULT_TITLE_OFFSET_MAX,
        help="warn (HEADER/TITLE-OFFCENTER) if the title block's centre is "
             "off the header's centre line by more than this fraction of "
             "header width -- a heavier side block (logo/venue/QR) is "
             "pulling the centred title aside (default %(default)s)",
    )
    ppl.add_argument(
        "--strict", action="store_true",
        help="exit non-zero when any warning is emitted",
    )
    ppl.set_defaults(func=_polish.cmd_polish)

    # --- verify-final ---------------------------------------------------
    pv = sub.add_parser(
        "verify-final",
        help="run pdfinfo + size/dimension/page checks on PDF",
    )
    pv.add_argument("pdf", help="path to poster.pdf")
    pv.add_argument(
        "--canvas", type=_canvas.parse_canvas_arg, default=None,
        help="expected canvas (e.g. '60x36in' or 'A0 portrait'); "
             "either this or --from-html is required",
    )
    pv.add_argument(
        "--from-html", default=None,
        help="read expected canvas from `@page { size }` in this "
             "HTML; mutually exclusive with --canvas",
    )
    pv.add_argument(
        "--dim-tol-in", type=float, default=0.05,
        help="dimension tolerance in inches (default 0.05)",
    )
    pv.add_argument(
        "--max-size-mb", type=float, default=20.0,
        help="max file size in MB (default 20)",
    )
    pv.add_argument(
        "--allow-rotated", action="store_true",
        help="accept swapped W/H even when PDF declares no page "
             "rotation (most posters should NOT need this)",
    )
    pv.set_defaults(func=_verify_final.cmd_verify_final)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
