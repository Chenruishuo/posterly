"""Soft visual-polish gate — runs at Step 6.

Gates the hard alignment gate cannot see:

  - **Gate A: figure sizing by aspect ratio.** A wide figure (AR > 1.3)
    rendered at 38% of card width wastes 60% of the column even when
    columns align. The defaults match the documented "aim for" lower
    bounds in SKILL.md so any figure inside the recommended range
    passes cleanly.
  - **Gate B: typography orphans + prose widows.** (1) ``1.18-1.30× ↑``
    whose ``↑`` wrapped alone onto its own line. Detected on elements with
    ``[class*="stat"]`` / ``[class*="num"]`` / ``.takeaway-num`` /
    ``.headline-num`` that end with a known orphan-prone glyph but
    lack ``white-space: nowrap``. (2) ``WIDOW``: a ``.callout`` /
    ``.body-text`` / ``.caption`` / ``.section-title`` / ``.card p`` /
    ``.card li`` / ``.fb-text`` (or a ``<br>`` segment of one) that wraps
    so its last visual line is a stranded runt -- filling less than 35%
    of the widest line (the framework banner ``.fb-text`` carries a higher
    ~80% bar: it must read as a filled rectangle, not merely avoid a runt).
    Judged by the last
    line's WIDTH as a fraction of the measure (not word count), so a short
    two-word tail flags and a single long word filling the line does not.
    A trailing figure/icon/table keeps the last line unjudgeable, but a short
    text tail ending in inline math (``by $\\lambda$.``) is caught.
    Long running prose (> the char cap) and GENERIC blocks -- any block-ish
    element holding worded text, discovered by geometry so custom-skeleton
    class names are covered -- are judged by the conservative bar only: a
    stranded SINGLE word under the runt width. (3) ``GLUE-CHAIN``: >= 3
    words fused with ``&nbsp;`` (the lazy widow "fix") -- the unbreakable
    unit wraps early as a whole and tears a hole in the line above; stat /
    math / list idioms are exempt (< 3 prose words, or a pure separator
    token in the chain). (4) ``TEXT-WRAP`` census: when >= 3 wrapped blocks
    carry neither ``text-wrap: pretty`` nor ``balance``, the templates'
    protective defaults were dropped (the custom-skeleton failure mode).
  - **Gate C: space-between fill.** ``justify-content: space-between``
    on a column with one short card produces a giant whitespace gap
    that reads as "this column ran out of things to say". Detected
    when the largest inter-card gap exceeds the column's stated
    ``row-gap`` by > 5% of column height. Two card-level siblings catch
    the same void inside a single card: ``CARD/TRAILING`` (blank BELOW
    the last line of a stretched card) and ``CARD/INNER-VOID`` (a gap in
    the MIDDLE of a card, below the last real block and above a child
    pinned to the bottom by ``margin-top: auto`` / ``justify-content:
    space-*`` -- the equal-height-row-with-unequal-content case, which
    ``CARD/TRAILING`` misses because the pinned tail makes trailing ~0).
    ``TRACK/INNER-VOID`` extends the same geometry to header/footer tracks
    (a vertical masthead spine / side rail), which are neither measure
    columns nor ``.card`` -- the wave-2 spine stretched by
    ``space-between`` shipped two ~500 px voids with every gate green.
  - **Gate G: composed text/ground contrast.** ``style_check`` verifies
    DECLARED token pairs; Gate G samples what actually RENDERED: each text
    run's foreground against the alpha-composited ground beneath it, WCAG
    ratio floored at ``--min-contrast`` (default 3.0 -- flags only
    unambiguous defects; deliberate muted inks sit ~3.5+). Text over
    images/gradients is skipped (verify those on the rendered crop). The
    recurring incident class: an inline emphasis/highlight class that sets
    a background but inherits text color from a different ground.

Warns by default; ``--strict`` to exit non-zero. Hard-fails if the
poster has no ``[data-measure-role]`` markup at all — a polish PASS on
"0 figures, 0 columns, 0 stat elements" would be misleading.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from . import canvas as _canvas
from . import preflight as _preflight
from . import render as _render


# Trailing glyphs that orphan when wrapped: arrows, multiplicative
# cross, division, plus-minus, footnote markers, degree, percent.
ORPHAN_GLYPHS = "↑↓↔×÷±§¶†‡*°%"

# A centered tall figure (AR<0.8) rendered below this fraction of card
# width is too small (wide symmetric side voids) -> FIG/TALL-SMALL. Single
# source of truth: poster_check.py's CLI default imports this constant, and
# the defensive getattr fallback below reuses it, so a programmatic caller
# with a pre-flag Namespace gets the SAME floor as the CLI.
DEFAULT_TALL_MIN_RATIO = 0.36

# Hero-stage letterbox (Gate A, hero branch). A hero figure is NOT exempt
# from sizing the way the old blanket `role=="hero": continue` assumed: a
# narrow-aspect image dropped into a wide-but-SHORT `.hero-stage` is height-
# constrained and leaves big symmetric side voids (e.g. a 2:1 panorama in a
# 5.5:1 stage fills ~35% of the width). HERO/STAGE-LETTERBOX fires when the
# picture fills < FILL of the stage width WHILE the stage is AR_MULT× wider
# (relative to the image AR) than the image needs, with symmetric side voids.
# A genuine full-bleed hero (image AR ~= stage AR, picture fills the width)
# never trips it.
DEFAULT_HERO_LETTERBOX_FILL = 0.55
DEFAULT_HERO_LETTERBOX_AR_MULT = 1.6

# Beside-text float void (Gate A2). A figure floated beside text
# (`data-fig-layout="beside-text"` inside a `.fig-wrap`) whose wrapping text
# stops more than this fraction of the figure's height short of the figure
# bottom leaves an L-shaped void below the text -> FIG/BESIDE-TEXT-VOID. The
# beside-text AR opt-out proves the figure is side-hugged but never checked
# the text actually fills the other side; this closes that residual.
DEFAULT_BESIDE_VOID_RATIO = 0.30

# Inner-card void (Gate C, third sibling of SPACE-BETWEEN / CARD/TRAILING).
# Those two catch a gap BETWEEN cards in a column and blank BELOW a card's
# last line; neither sees a void in the MIDDLE of a card. When a card is
# stretched taller than its content (an equal-height grid row with unequal
# content) and a child is pinned to the bottom -- `margin-top: auto`, or a
# `justify-content: space-*` on the card itself -- the slack opens between
# two children, below the last real block and above the pinned one, so the
# trailing-below-last reads ~0 and CARD/TRAILING stays silent. Detected by
# geometry (largest inter-child vertical gap minus the card's stated
# row-gap), so the mechanism (auto-margin / space-between / stray margin)
# does not matter. The scan covers every `.card` (not only the
# data-measure-role-tagged ones), so an agent-authored feature band whose
# cards carry only the `.card` class is still checked. Flag when the excess
# is BOTH > this fraction of card height AND > the px floor (the floor keeps
# a sub-line gap on a small card from tripping it).
DEFAULT_CARD_INNER_VOID = 0.08
DEFAULT_CARD_INNER_VOID_PX = 24.0

# Header-logo gates (Gate E). Same single-source pattern as above: the
# CLI defaults in poster_check.py import these, and the getattr fallbacks
# in cmd_polish reuse them. Calibrated against the template size classes
# (60x36in landscape header ~1496u: logo-wide caps at 300u < 22%;
# 24x36in portrait header ~586u: wide cap 125u < 22%) so a logo sized by
# a recommended class never trips its own gate.
DEFAULT_LOGO_MAX_WIDTH_RATIO = 0.22
DEFAULT_LOGO_QR_TOL = 0.15
# A logo-wide wordmark is INTENTIONALLY shorter than the QR for visual
# balance (58/85 = 0.68), so it gets a height BAND relative to the QR
# instead of the strict match above.
LOGO_WIDE_QR_BAND = (0.55, 0.85)
DEFAULT_RIGHTBLOCK_MAX_RATIO = 0.32
DEFAULT_TITLE_MIN_RATIO = 0.45
# Vertical-rail masthead detection (Gate E). Every Gate E calibration
# above is written for a HORIZONTAL masthead strip (logo width as % of
# header width, QR-height-matched logo row, side blocks squeezing a
# centred title). A portrait title-spine masthead (DESIGN-AXES Axis 1,
# P5) is a tall narrow RAIL -- those ratios are meaningless there and
# every one of them mis-fires. A rail is unmistakable in practice
# (P5's ~3.8in x ~33in rail is ~9:1; a portrait strip masthead is
# ~1:7 the other way), so a modest 1.5:1 height-over-width threshold
# separates them with a wide margin. In rail mode the horizontal
# calibrations are SKIPPED and replaced by rail checks: logos capped by
# the rail's content width, and blocks checked against all four content
# edges. LOGO/BROKEN is unconditional in both modes.
RAIL_MIN_ASPECT = 1.5

# Title-centring gate (Gate E). The shipped header centres the title with
# `1fr minmax(50%, auto) 1fr`; a side block (logo / venue badge / QR) heavier
# than the other still pulls the centred track aside. Soft WARN when the
# title-block centre is off the header centre by more than this fraction of
# header width -- a nudge to rebalance the header WHEN logo/QR sizing allows,
# not a hard rule (sizing + layout win; centring is best-effort).
DEFAULT_TITLE_OFFSET_MAX = 0.03

# Banner image-slot gate (Gate F). A method figure in the optional framework
# banner whose flex-ITEM ("slot") is much wider than the image itself wastes
# banner width and steals room from the body text/stats (the banner figure is
# captionless by default; a needless caption is the usual cause). Two
# shapes feed one warning: (1) the image is pinned to one side of an over-wide
# slot -> a big one-sided dead band (the visible "whitespace beside the
# figure"); (2) the image is centred but a long single-line caption still
# stretches the slot to the caption's width (the "half-fix" -- adding
# margin:auto evens the gaps but the caption keeps setting the width). Images
# narrower/shorter than these floors are inline icons, not method figures, and
# are skipped. The shipped `banner-figure` component (`width:min-content`)
# collapses the slot to the image, so a correct banner never trips this.
DEFAULT_BANNER_SLOT_MIN_PIC_W = 240.0
DEFAULT_BANNER_SLOT_MIN_PIC_H = 80.0

# Gate thresholds whose CLI defaults previously lived only in poster_check's
# argparse `default=`. Kept here so callers WITHOUT a polish arg namespace --
# `measure --with-polish` runs the polish gates on the SAME rendered page via
# default_polish_args() -- use the exact same numbers; poster_check points its
# `default=` at these constants so the two entry points cannot drift.
DEFAULT_WIDE_MIN_RATIO = 0.65
DEFAULT_TALL_MAX_RATIO = 0.70
DEFAULT_SQUARE_MIN_RATIO = 0.55
DEFAULT_MAX_SPACE_BETWEEN_FILL = 0.05
DEFAULT_MAX_CARD_TRAILING = 0.10

# Composed-contrast gate (Gate G). style_check verifies DECLARED token pairs;
# this verifies the COMPOSED result at render time -- the recurring incident
# class is an inline emphasis/highlight class whose background lands under
# text whose color was designed for a DIFFERENT ground (wave-1: rust lead-ins
# on a steel-blue callout fill, 1.2:1; wave-2: inherited white '4.05' on a
# pale .mark highlight, 1.4:1). 3.0 is deliberately below WCAG-AA body (4.5):
# poster text is large-format and deliberate muted-ink designs sit ~3.5-4.5,
# so the gate flags only unambiguous defects. Raise via --min-contrast for a
# stricter pass.
DEFAULT_MIN_CONTRAST = 3.0

# text-wrap census (Gate B advisory). Warn only when at least this many
# WRAPPED text blocks carry neither `text-wrap: pretty` nor `balance` -- one
# or two unprotected blocks is normal (a deliberate tight lockup); a poster
# full of them has dropped the templates' protective defaults (the usual
# custom-skeleton failure: wave-2's band-rows poster shipped ZERO text-wrap
# declarations and stranded both a body-text widow and a title 'Matching').
DEFAULT_MIN_UNPROTECTED_WRAPS = 3


from .textutil import ascii_safe


def _eprint(*args: Any, **kw: Any) -> None:
    print(*args, file=sys.stderr, **kw)


_POLISH_JS = r"""
() => {
  // ---- 1) Figure sizing ----
  // For each card, list every <img> with rendered size, the card's
  // bounding width (the "budget"), and natural dimensions for AR.
  const figures = [];
  document.querySelectorAll('[data-measure-role="card"]')
    .forEach((card, ci) => {
      const cr = card.getBoundingClientRect();
      const cw = cr.width;
      card.querySelectorAll('img').forEach(img => {
        const r = img.getBoundingClientRect();
        if (r.width < 50) return;  // skip inline icons
        figures.push({
          card_index: ci,
          role: 'card',
          src: img.getAttribute('src') || '',
          alt: img.getAttribute('alt') || '',
          fig_layout: img.getAttribute('data-fig-layout') || '',
          // object-fit + side offsets let the Python gate see picture-level
          // letterboxing (contain voids INSIDE a full-width box) and tell a
          // genuine beside-text layout (hugged to one side) from a centred
          // figure mis-tagged to mute the warning.
          obj_fit: window.getComputedStyle(img).objectFit || '',
          off_left: r.left - cr.left,
          off_right: cr.right - r.right,
          rendered_w: r.width,
          rendered_h: r.height,
          card_w: cw,
          natural_w: img.naturalWidth || 0,
          natural_h: img.naturalHeight || 0,
        });
      });
    });
  // Hero-panel images (the main figure of a hero-layout poster) get the
  // broken-image check too -- a blank centerpiece is the worst failure
  // mode and the card-only scan used to miss it. AR sizing gates are
  // skipped for these on the Python side (they are framed as % of card
  // width, which the full-bleed hero panel doesn't have).
  document.querySelectorAll('[data-measure-role="hero"]')
    .forEach(hero => {
      const hw = hero.getBoundingClientRect().width;
      hero.querySelectorAll('img').forEach(img => {
        const r = img.getBoundingClientRect();
        if (r.width < 50) return;  // skip venue badges / inline icons
        // The "stage" is the immediate figure box the image is letterboxed
        // INSIDE (`.hero-stage` in the hero template), falling back to the
        // hero panel itself. The wide-short-stage / narrow-image side void
        // is measured against THIS box and the image's offsets within it --
        // not the whole hero -- so HERO/STAGE-LETTERBOX can replace the old
        // blanket hero skip without over-reaching.
        const stage = img.closest('.hero-stage') || hero;
        const sr = stage.getBoundingClientRect();
        figures.push({
          card_index: -1,
          role: 'hero',
          src: img.getAttribute('src') || '',
          alt: img.getAttribute('alt') || '',
          fig_layout: img.getAttribute('data-fig-layout') || '',
          obj_fit: window.getComputedStyle(img).objectFit || '',
          off_left: r.left - sr.left,
          off_right: sr.right - r.right,
          rendered_w: r.width,
          rendered_h: r.height,
          card_w: hw,
          stage_w: sr.width,
          stage_h: sr.height,
          natural_w: img.naturalWidth || 0,
          natural_h: img.naturalHeight || 0,
        });
      });
    });
  // Band images (full-width portrait content band, DESIGN-AXES Axis 1
  // portrait translations) take the same hero path: broken-image check
  // plus the wide-short-stage letterbox test, measured against the
  // nearest stage box (`.band-stage`, or `.hero-stage` when a hero
  // construction was re-used inside the band) falling back to the band.
  document.querySelectorAll('[data-measure-role="band"]')
    .forEach(band => {
      const bw = band.getBoundingClientRect().width;
      band.querySelectorAll('img').forEach(img => {
        const r = img.getBoundingClientRect();
        if (r.width < 50) return;  // skip venue badges / inline icons
        const stage = img.closest('.band-stage, .hero-stage') || band;
        const sr = stage.getBoundingClientRect();
        figures.push({
          card_index: -1,
          role: 'band',
          src: img.getAttribute('src') || '',
          alt: img.getAttribute('alt') || '',
          fig_layout: img.getAttribute('data-fig-layout') || '',
          obj_fit: window.getComputedStyle(img).objectFit || '',
          off_left: r.left - sr.left,
          off_right: sr.right - r.right,
          rendered_w: r.width,
          rendered_h: r.height,
          card_w: bw,
          stage_w: sr.width,
          stage_h: sr.height,
          natural_w: img.naturalWidth || 0,
          natural_h: img.naturalHeight || 0,
        });
      });
    });

  // ---- 2) Orphan-prone text elements ----
  const sel = '[class*="stat"], [class*="num"], .num, .takeaway-num,'
            + ' .headline-num';
  const seen = new Set();
  const orphans = [];
  document.querySelectorAll(sel).forEach(el => {
    if (seen.has(el)) return;
    seen.add(el);
    const txt = (el.innerText || '').replace(/\s+$/, '');
    if (!txt || txt.length > 80) return;
    const cs = window.getComputedStyle(el);
    orphans.push({
      tag: el.tagName.toLowerCase(),
      cls: el.className || '',
      text: txt,
      ws: cs.whiteSpace || '',
    });
  });

  // ---- 3) Space-between fill ----
  const cols = [];
  document.querySelectorAll('[data-measure-role="column"]')
    .forEach((col, ci) => {
      const cs = window.getComputedStyle(col);
      if (cs.justifyContent !== 'space-between') return;
      const colR = col.getBoundingClientRect();
      const children = Array.from(col.children).map(c => {
        const r = c.getBoundingClientRect();
        return {top: r.top, bottom: r.bottom, h: r.height};
      }).filter(c => c.h > 0);
      if (children.length < 2) return;
      const gapPx = parseFloat(cs.rowGap || cs.gap || '0') || 0;
      let maxExcess = 0;
      let pairIdx = -1;
      for (let i = 1; i < children.length; i++) {
        const actual = children[i].top - children[i - 1].bottom;
        const excess = actual - gapPx;
        if (excess > maxExcess) {
          maxExcess = excess;
          pairIdx = i;
        }
      }
      cols.push({
        column_index: ci,
        column_h: colR.height,
        stated_gap_px: gapPx,
        max_excess_px: maxExcess,
        pair_idx: pairIdx,
      });
    });

  // ---- 4) Card trailing whitespace (single stretched card) ----
  // A card with flex:1 (or any stretch-to-fill) whose content is top-
  // packed leaves blank space below the last line. `measure` only checks
  // the card's bottom edge so it passes; Gate C only looks BETWEEN cards.
  // Skip cards that distribute space on purpose (space-* / center / end)
  // -- that is Gate C's territory or an intentional layout.
  const cards = [];
  document.querySelectorAll('[data-measure-role="card"]')
    .forEach((card, ci) => {
      const cs = window.getComputedStyle(card);
      const jc = cs.justifyContent || '';
      if (jc.indexOf('space') !== -1 || jc === 'center'
          || jc === 'end' || jc === 'flex-end') return;
      const cr = card.getBoundingClientRect();
      if (cr.height <= 0) return;
      const padB = parseFloat(cs.paddingBottom) || 0;
      const padT = parseFloat(cs.paddingTop) || 0;
      const borderB = parseFloat(cs.borderBottomWidth) || 0;

      // Is `node` inside an absolutely/fixed-positioned subtree within the
      // card? A corner badge / QR / watermark sits at the card bottom but
      // is NOT the normal-flow content bottom -- counting it would mask a
      // top-packed void above it (false negative). Walk parents to card.
      const inAbs = (node) => {
        let el = node.nodeType === 1 ? node : node.parentElement;
        while (el && el !== card) {
          const pos = window.getComputedStyle(el).position;
          if (pos === 'absolute' || pos === 'fixed') return true;
          el = el.parentElement;
        }
        return false;
      };

      // Bottom-most rendered CONTENT = max over three sources (each kept
      // via `maxB`, so adding a source can only RAISE the content bottom,
      // never hide a void):
      //   (1) TEXT, via Range -- a plain-text tail that wraps onto a line
      //       BELOW an inline <span>/<b>/<code> is invisible to an element
      //       scan (its parent <p> has element children so it's skipped,
      //       and the inline leaf sits on an earlier line) -> undershoot.
      //   (2) REPLACED media (img/svg/canvas/...) -- even when it has child
      //       nodes (e.g. <svg> wrapping <path>s) and so isn't a leaf.
      //   (3) LEAF element boxes (no element children) -- re-covers a pure-
      //       CSS diagram node (an empty <div> bar/box) that carries no
      //       text and isn't replaced, which (1)+(2) alone would miss.
      // Non-leaf, non-replaced CONTAINERS are skipped: a stretched wrapper
      // box would over-measure to the card bottom and mask the void.
      let maxB = cr.top + padT;
      const bump = (r) => {
        if (r && r.height > 0 && r.bottom > maxB) maxB = r.bottom;
      };
      const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
      for (let tn = walker.nextNode(); tn; tn = walker.nextNode()) {
        if (!tn.nodeValue || !tn.nodeValue.trim()) continue;
        if (inAbs(tn)) continue;
        const rng = document.createRange();
        rng.selectNodeContents(tn);
        const rects = rng.getClientRects();
        for (let i = 0; i < rects.length; i++) bump(rects[i]);
      }
      const REPLACED = /^(IMG|SVG|CANVAS|VIDEO|IFRAME|HR|OBJECT|EMBED)$/;
      card.querySelectorAll('*').forEach(el => {
        if (inAbs(el)) return;
        // tagName is upper-case for HTML, but case-preserved (lower) for
        // SVG elements -- normalise before the replaced-tag test.
        if (!REPLACED.test(el.tagName.toUpperCase())) {
          if (el.children.length) {
            return;  // a non-replaced container: skip (only leaves + media)
          }
          // A text-bearing leaf with NO visible paint of its own
          // (transparent bg, no border/shadow): its visual content is
          // exactly its text, which the Range walk above already
          // measured. Counting the whole box would let a tall reserved
          // box (e.g. the keybox label's `min-height: 2lh` slot) read
          // as "content" and mask a real trailing void. A PAINTED leaf
          // (callout pill, tinted bar) keeps the box bump -- its
          // background visibly extends to the box edge.
          if ((el.textContent || '').trim()) {
            const ls = window.getComputedStyle(el);
            const bg = ls.backgroundColor || '';
            // An invisible box paints nothing regardless of bg/border.
            const invisible = ls.visibility === 'hidden'
              || parseFloat(ls.opacity) === 0;
            const painted = !invisible && (
              (bg && bg !== 'transparent'
                  && bg !== 'rgba(0, 0, 0, 0)')
              || (ls.backgroundImage && ls.backgroundImage !== 'none')
              || (ls.boxShadow && ls.boxShadow !== 'none')
              || (parseFloat(ls.borderTopWidth) || 0) > 0
              || (parseFloat(ls.borderRightWidth) || 0) > 0
              || (parseFloat(ls.borderBottomWidth) || 0) > 0
              || (parseFloat(ls.borderLeftWidth) || 0) > 0);
            if (!painted) return;
          }
        }
        bump(el.getBoundingClientRect());
      });

      cards.push({
        card_index: ci,
        card_h: cr.height,
        trailing_px: (cr.bottom - padB - borderB) - maxB,
      });
    });

  // ---- 5) <br> as a direct child of a flex container ----
  // A <br> that is an in-flow child of display:flex|inline-flex is
  // blockified into a flex ITEM and stops creating a line break -- so
  // intended multi-line content (e.g. an icon + label stacked with <br>)
  // silently collapses onto one row. `measure` can't see it (card bottom
  // is unchanged); only the eye catches it. Report each offending flex
  // parent once. Even in flex-direction:column the <br> does nothing (the
  // text runs already stack as separate items); row is where it visibly
  // breaks, so we report the direction to make the fix obvious.
  const flexbr = [];
  const seenFlexBr = new Set();
  document.querySelectorAll('br').forEach(br => {
    const parent = br.parentElement;
    if (!parent || seenFlexBr.has(parent)) return;
    const cs = window.getComputedStyle(parent);
    if (cs.display === 'flex' || cs.display === 'inline-flex') {
      seenFlexBr.add(parent);
      flexbr.push({
        tag: parent.tagName.toLowerCase(),
        cls: parent.className || '',
        dir: cs.flexDirection || 'row',
      });
    }
  });

  // ---- 6) Header logos / QR / title squeeze ----
  // Affiliation + venue logos live in the header, outside any card/hero,
  // so blocks 1-5 never see them: a 404'd logo prints blank silently and
  // an oversized wordmark silently crowds the title (the header grid is
  // `1fr minmax(50%, auto) 1fr`: the title sits in an equal-tracks-centred
  // column floored at 50%, so instead of silently shrinking the title an
  // oversized side block is caught by the right-block ratio (right side) or
  // the title-centre offset (either side -- a fat left venue badge too)).
  // Collect geometry for Gate E. Everything
  // is scoped UNDER the header role: a footer .qr-block or a card-body
  // .logo-slot is not a header asset and must not drive these gates.
  const header = document.querySelector('[data-measure-role="header"]');
  const headerRect = header ? header.getBoundingClientRect() : null;
  const headerW = headerRect ? headerRect.width : 0;
  // height too: a vertical-rail masthead (portrait P5 title spine) is
  // detected Python-side from the aspect ratio and swaps the horizontal
  // calibrations for rail checks.
  const headerH = headerRect ? headerRect.height : 0;
  // poster-centre x of the header box, for the title-centring gate below
  const headerCx = headerRect ? headerRect.left + headerRect.width / 2 : 0;
  // content-box edges (inside border + padding), for the overflow gate;
  // top/bottom feed the rail-mode vertical overflow check only.
  let headerContentLeft = 0, headerContentRight = 0;
  let headerContentTop = 0, headerContentBottom = 0;
  if (header && headerRect) {
    const cs = getComputedStyle(header);
    headerContentLeft = headerRect.left
      + (parseFloat(cs.borderLeftWidth) || 0) + (parseFloat(cs.paddingLeft) || 0);
    headerContentRight = headerRect.right
      - (parseFloat(cs.borderRightWidth) || 0) - (parseFloat(cs.paddingRight) || 0);
    headerContentTop = headerRect.top
      + (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.paddingTop) || 0);
    headerContentBottom = headerRect.bottom
      - (parseFloat(cs.borderBottomWidth) || 0)
      - (parseFloat(cs.paddingBottom) || 0);
  }
  const logos = [];
  const qrs = [];
  const headerBlocks = [];
  if (header) {
    // querySelectorAll dedupes, so an img matching BOTH selectors (a
    // .logo-slot nested inside .venue-badge) is collected exactly once;
    // closest() then resolves its scope (venue wins -- the badge sits
    // left of the title at its own scale).
    header.querySelectorAll('.logo-slot img, .venue-badge img')
      .forEach(img => {
        const r = img.getBoundingClientRect();
        if (r.width < 20) return;  // skip stray inline marks
        const slot = img.closest('.logo-slot')
                  || img.closest('.venue-badge');
        logos.push({
          src: img.getAttribute('src') || '',
          rendered_w: r.width,
          rendered_h: r.height,
          natural_w: img.naturalWidth || 0,
          natural_h: img.naturalHeight || 0,
          slot_classes: slot ? (slot.className || '') : '',
          venue: !!img.closest('.venue-badge'),
          stacked: !!img.closest('.logo-row.logo-stack'),
          has_chip: !!img.closest('.logo-chip'),
        });
      });
    header.querySelectorAll('.qr-block img').forEach(img => {
      const r = img.getBoundingClientRect();
      if (r.width < 20) return;
      qrs.push({rendered_h: r.height});
    });
    // .right-stack is the stacked variant some posters use in place of
    // .right-block -- cover both, or those posters skip the squeeze gate.
    // .venue-badge (the left block) is collected too, only for the overflow
    // gate (its width never drives the right-block / title-min ratios).
    header.querySelectorAll('.venue-badge, .right-block, .right-stack, .title-block')
      .forEach(el => {
        const r = el.getBoundingClientRect();
        let kind = 'right';
        if (el.classList.contains('title-block')) kind = 'title';
        else if (el.classList.contains('venue-badge')) kind = 'left';
        headerBlocks.push({
          cls: el.className || '',
          kind: kind,
          w: r.width,
          cx: r.left + r.width / 2,
          left: r.left,
          right: r.right,
          top: r.top,
          bottom: r.bottom,
        });
      });
  }

  // ---- 7) Beside-text float void ----
  // A figure floated beside text (`.fig-wrap` > `figure.ff-fig` with the
  // img tagged data-fig-layout="beside-text") whose wrapping text is SHORT
  // leaves an L-shaped void: the text stops beside the figure's upper half
  // and below it (still beside the figure's lower half) is blank. Measure
  // how far the wrapping text falls short of the figure bottom. Text is the
  // fig-wrap's own text EXCLUDING the figure's caption (fig.contains). If
  // the text genuinely flows past the figure bottom, text_bottom >=
  // fig_bottom and the Python side reads a non-positive deficit -> no warn.
  const besideVoids = [];
  document.querySelectorAll('.fig-wrap').forEach((wrap, wi) => {
    const fig = wrap.querySelector('figure.ff-fig, .ff-fig');
    if (!fig) return;
    const img = fig.querySelector('img[data-fig-layout="beside-text"]');
    if (!img) return;  // only the marked float layout, not a generic wrap
    const fr = fig.getBoundingClientRect();
    if (fr.height <= 0) return;
    // Only count line rects that are genuinely BESIDE the figure: they must
    // (a) overlap the figure vertically AND (b) sit clear of it horizontally
    // (entirely to one side). A line that wraps BELOW the figure runs full
    // width -- it overlaps the figure horizontally and/or starts past its
    // bottom -- so it is excluded, and trailing below-figure text can't mask
    // a side void (the deficit reflects only how far the SIDE text reaches).
    let textBottom = -Infinity;
    const heights = [];
    const walker = document.createTreeWalker(wrap, NodeFilter.SHOW_TEXT);
    for (let tn = walker.nextNode(); tn; tn = walker.nextNode()) {
      if (!tn.nodeValue || !tn.nodeValue.trim()) continue;
      if (fig.contains(tn)) continue;  // skip the figure's own caption text
      const rng = document.createRange();
      rng.selectNodeContents(tn);
      const rects = rng.getClientRects();
      for (let i = 0; i < rects.length; i++) {
        const rc = rects[i];
        if (rc.height <= 0) continue;
        const overlapsV = (rc.top < fr.bottom - 1) && (rc.bottom > fr.top + 1);
        const clearsH = (rc.left >= fr.right - 1) || (rc.right <= fr.left + 1);
        if (!overlapsV || !clearsH) continue;  // below / behind the figure
        if (rc.bottom > textBottom) textBottom = rc.bottom;
        heights.push(rc.height);
      }
    }
    // Median line height -- robust to a single tall inline element (MathJax,
    // an enlarged span) that a max() would let inflate and wrongly silence a
    // real void via the 1.5-line guard on the Python side.
    heights.sort((a, b) => a - b);
    const lineH = heights.length
      ? heights[Math.floor((heights.length - 1) / 2)] : 0;
    besideVoids.push({
      wrap_index: wi,
      src: img.getAttribute('src') || '',
      fig_bottom: fr.bottom,
      fig_h: fr.height,
      text_bottom: (textBottom === -Infinity) ? null : textBottom,
      line_h: lineH,
    });
  });

  // ---- 8) Prose widows: a wrapped text block whose LAST visual line is a
  //         stranded RUNT -- it fills less than RUNT_FRAC of the typeset
  //         measure. `measure` checks card bottoms; section 2's orphan scan
  //         only sees a trailing GLYPH on a stat/num element. Neither sees a
  //         `.callout`/`.body-text`/`.caption`/`.section-title`/`.card p`/`.card li`/
  //         `.fb-text` that wraps to a short last line -- the artefact SKILL.md Gate
  //         B forbids.
  //         We judge by the last line's WIDTH as a fraction of the widest line
  //         (NOT word count): a short two-word tail is as ugly as a one-word
  //         one, while a single long word that fills the line is not stranded.
  //         The framework banner (.fb-text) is the poster's most prominent block,
  //         so it gets a much higher bar (BANNER_FILL_FRAC): not just "not a runt"
  //         but a near-full last line -- a filled rectangle.
  //         Robust to inline <strong>/<code> splitting a word's rects, to
  //         `text-align: justify`, and to sub-pixel / mixed-font-size line tops.
  const widows = [];
  const RUNT_FRAC = 0.35;   // last line < 35% of the measure = stranded runt
  // The framework banner (.fb-text) is the poster's single most prominent text
  // block; a merely "not-a-runt" last line still reads as a ragged box there. It
  // gets a much higher bar -- aim for a near-full last line (a filled rectangle),
  // reached by reflowing the text: tune the .fb-text width, bump its font size,
  // and/or expand/trim the wording -- any one or a moderate mix (SKILL.md Gate B),
  // NOT by justification / letter-spacing padding, nor by pushing one lever to an
  // extreme (e.g. a blown-up font) just to pass. Still a soft warning, never a hard fail.
  const BANNER_FILL_FRAC = 0.80;
  const WIDOW_SEL = '.callout, .body-text, .caption, .section-title,'
                  + ' .card p, .card li, .fb-text';
  // Glue chains: >=3 words fused with &nbsp; form one unbreakable unit that
  // wraps EARLY as a whole, tearing a hole in the line above -- the lazy
  // widow "fix" the wave-2 posters shipped. Collected during the same walk.
  const glueChains = [];
  // text-wrap census: wrapped prose with neither `pretty` nor `balance` --
  // custom skeletons routinely drop the templates' protective declarations
  // (one wave-2 poster shipped ZERO text-wrap rules). Aggregated, not
  // per-element, so it nudges instead of flooding.
  const wrapCensus = [];

  // Candidates come from TWO pools:
  //   (1) the whitelisted prose classes above -- full RUNT_FRAC bar;
  //   (2) every OTHER block-ish element that directly holds worded text,
  //       discovered by GEOMETRY, not class name -- the 8-axis custom
  //       skeletons author their own classes (.band-lede, .mh-sub, ...), so a
  //       class whitelist goes blind exactly where wave-2's widows happened
  //       (a stranded 'Matching' in a custom masthead subtitle). Generic
  //       blocks are judged by the CONSERVATIVE bar only (single stranded
  //       word), so unknown block types can't flood the report.
  const candidates = [];
  const wlSet = new Set();
  document.querySelectorAll(WIDOW_SEL).forEach(el => {
    // Scan only the most specific prose leaf: if this element CONTAINS another
    // candidate (a .callout wrapping a <p class="body-text">), skip it -- the
    // descendant is scanned on its own, so we never double-report one widow.
    if (el.querySelector(WIDOW_SEL)) return;
    wlSet.add(el);
    candidates.push({el, generic: false});
  });
  {
    const root = document.querySelector('[data-measure-role="poster"]')
              || document.body;
    // "Blocky" = element that establishes its own line box flow; inline
    // descendants (<strong>, <span>) stay part of the parent's paragraph.
    const blockyCache = new Map();
    const isBlocky = (el) => {
      if (blockyCache.has(el)) return blockyCache.get(el);
      const d = getComputedStyle(el).display;
      // inline-* (inline, inline-block, inline-flex, inline-grid) all flow
      // INSIDE the parent's line boxes -- treating them as blocks would make
      // an inline-block chip a candidate of its own and, via the
      // innermost-only rule below, DELETE the parent paragraph from the
      // scan (its widow/census/glue coverage with it).
      const b = !d.startsWith('inline') && d !== 'contents' && d !== 'none'
             && !d.startsWith('ruby');
      blockyCache.set(el, b);
      return b;
    };
    // Nearest blocky ancestor of each worded text node = its paragraph box.
    const candSet = new Set();
    const twAll = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let tn = twAll.nextNode(); tn; tn = twAll.nextNode()) {
      if (!/[\p{L}\p{N}]{2}/u.test(tn.nodeValue || '')) continue;
      let el = tn.parentElement;
      if (!el) continue;
      // Math/SVG internals are not prose; TABLE cells wrap short lines by
      // design (the widow contract doesn't fit them -- contrast still covers
      // their text via the separate scan below).
      if (el.closest('mjx-container, .MathJax, math, svg, table,'
                     + ' script, style')) continue;
      while (el && el !== root && !isBlocky(el)) el = el.parentElement;
      if (el) candSet.add(el);
    }
    // Innermost blocks only: a wrapper holding both direct text and a texted
    // block child would judge a "last line" that isn't visually last.
    const hasCandDesc = new Set();
    candSet.forEach(el => {
      for (let p = el.parentElement; p; p = p.parentElement) {
        if (candSet.has(p)) hasCandDesc.add(p);
      }
    });
    candSet.forEach(el => {
      if (hasCandDesc.has(el)) return;
      if (wlSet.has(el) || el.closest(WIDOW_SEL)) return;  // pool (1) owns it
      if (el.querySelector(WIDOW_SEL)) return;             // wraps a pool-(1) leaf
      if (el.closest('[data-vrail-title]')) return;        // deliberate stack
      candidates.push({el, generic: true});
    });
  }

  candidates.forEach(({el, generic}) => {
    // A vrail rail title is a DELIBERATELY narrow stacked column
    // (each word on its own horizontal line, an over-long word broken with a soft
    // hyphen at a syllable boundary the AGENT judges). Its short last line is
    // intentional, not a runt -- where to break is an authoring judgment the agent
    // makes, not a geometry a gate can score -- so it is marked data-vrail-title to
    // opt out of the widow check. See SKILL.md Gate B.
    if (el.hasAttribute('data-vrail-title')) return;
    const cs = getComputedStyle(el);
    // text-wrap protection census (fed to the aggregated TEXT-WRAP note):
    // `pretty` guards the last-line orphan on prose, `balance` evens centered
    // display text. Chromium exposes the computed value on `textWrap` (older)
    // or `text-wrap-style` (newer split property) -- read both.
    const twStyle = (cs.textWrap || cs.getPropertyValue('text-wrap')
                     || cs.getPropertyValue('text-wrap-style') || '');
    const wrapProtected = /pretty|balance/.test(twStyle);
    let censusCounted = false;
    const ws = (cs.whiteSpace || '').toLowerCase();
    if (ws.indexOf('nowrap') !== -1 || ws.indexOf('pre') !== -1) return;
    if ((cs.direction || '') === 'rtl') return;               // "last word" geometry unclear in RTL
    const wm = cs.writingMode || '';
    if (wm && wm.indexOf('horizontal') === -1) return;        // vertical text out of scope
    // Math / figure elements do NOT hide the whole block any more (a caption
    // mixing inline $math$ with a lone trailing word slipped through that
    // blanket skip -- the eb181286 "one." incident). They join the line model
    // as OPAQUE cells: their text (if any) stays out of the token stream, but
    // their rects vote in line grouping. A last line is then skipped only when
    // it carries figure/icon/table MEDIA, or is opaque with no real WORD -- a
    // lone trailing equation, even with a sentence period (see the last-line
    // gate below); a text tail with a real word ending in math IS judged.
    const OPAQUE = 'mjx-container, .MathJax, math, img, svg, canvas, table';
    // Of those, FIGURE-class opaques (image / icon / canvas / table) are real
    // media, not prose: a last line trailing one is unjudgeable (its width as a
    // "runt" is meaningless and a trailing inline icon may be deliberate). Inline
    // MATH (mjx-container / .MathJax / math) is NOT media -- it reads as part of
    // the sentence, so a short text fragment ending in math ("by $\\lambda$.")
    // IS a stranded runt and must be judged.
    const MEDIA = 'img, svg, canvas, table';
    // Display text (.caption / .callout / .fb-text) gets a higher length cap
    // than running prose: a short stranded last line is prominent in display
    // copy even when the block is long -- a caption under a figure, or the
    // framework-banner blurb. The 220-char cap was exactly why an incident
    // caption (231 chars) and a 269-char banner .fb-text (whose last line filled
    // only 17% of the measure) were never measured.
    const cap = (el.matches('.caption, .callout') || el.closest('.fb-text')) ? 400 : 220;

    // Split the element's own text into `<br>`-delimited paragraphs, each
    // keeping a flat string + a DOM map (so a word split across inline tags
    // stays ONE token) + the opaque elements seen in that segment. A widow
    // can sit at the end of an EARLY segment (the statement above a
    // <br>question), so we check every segment, not just the block's final
    // visual line.
    const paras = [];
    let cur = {flat: '', segs: [], ops: []};
    const tw = document.createTreeWalker(
      el, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      if (n.nodeType === 1) {
        // OPAQUE interiors are structure we must not interpret: a <br> inside
        // a <table> cell must NOT split the OUTER prose into segments (it
        // would orphan the trailing text into a 1-token segment and mask a
        // real widow). Skip everything below an opaque root; the root itself
        // passes this test and is recorded.
        if (n.parentElement && n.parentElement.closest(OPAQUE)) continue;
        if (n.tagName === 'BR') { paras.push(cur); cur = {flat: '', segs: [], ops: []}; continue; }
        // Record the OUTERMOST opaque element (nested <svg> in <mjx-container>
        // was filtered above). visibility:hidden opaques still occupy layout
        // but paint nothing -- a lone word next to one IS visually stranded,
        // so they must not vote.
        if (n.matches && n.matches(OPAQUE)
            && getComputedStyle(n).visibility !== 'hidden') {
          cur.ops.push(n);
        }
        continue;
      }
      // Skip the section-number badge (.num): a flex item whose center-y would
      // corrupt line grouping and whose digit would fuse into the first token.
      if (n.parentElement && n.parentElement.closest('.num')) continue;
      // Text living INSIDE an opaque element (a <table> cell, MathML token)
      // is represented by the opaque rect, not the token stream.
      if (n.parentElement && n.parentElement.closest(OPAQUE)) continue;
      const v = n.nodeValue;
      if (!v) continue;
      cur.segs.push({node: n, base: cur.flat.length, text: v});
      cur.flat += v;
    }
    paras.push(cur);

    paras.forEach(para => {
      const norm = para.flat.replace(/\s+/g, ' ').trim();
      if (norm.length === 0) return;
      // ---- GLUE-CHAIN: >=3 words fused with &nbsp; (U+00A0). A 2-token glue
      // is the documented legit use (marker/stat cell); a longer chain is an
      // unbreakable unit that wraps EARLY as a whole and tears a hole in the
      // line above -- the lazy widow "fix". Fused PROSE is the problem;
      // stat / math / list idioms are legit glue, so a chain flags only when
      // it carries >= 3 prose words (>= 2 consecutive letters) AND no pure
      // separator token: "alpha = 4" (no prose words), "> GRPO 3.93 > EMPO
      // 3.80." (2), and a middot-joined footer contact strip (separator
      // tokens) all stay quiet; "holds length and keeps improving." flags.
      // Runs BEFORE the length caps below -- chains hide in long prose too.
      {
        const chainRe = /(?:\S+\u00A0+){2,}\S+/g;
        let cm;
        while ((cm = chainRe.exec(para.flat)) !== null) {
          const words = cm[0].split(/\u00A0+/);
          const proseWords =
            words.filter(w => /[\p{L}]{2}/u.test(w)).length;
          // A list/contact-strip separator ANYWHERE in the chain (middot,
          // pipe, slash, en/em dash -- deliberately NOT the word-internal
          // hyphen: a fused hyphenated compound is still fused prose) marks
          // a joined-list idiom -- footers glue `&nbsp;\u00B7` tight against
          // the next token, so a token-level "pure separator" test misses
          // them.
          const hasSep = /[\u00B7|/\u2014\u2013]/.test(cm[0]);
          if (proseWords < 3 || hasSep) continue;
          glueChains.push({
            tag: el.tagName.toLowerCase(),
            cls: el.className || '',
            chain: cm[0].replace(/\u00A0+/g, ' ').slice(0, 60),
            words: words.length,
          });
        }
      }
      // Long running prose used to be SKIPPED outright (norm.length > cap) --
      // which is exactly how a 262-char .body-text shipped a stranded
      // 'AIME24/25).' last line. Long prose (and every generic, unlisted-class
      // block) is now judged by the CONSERVATIVE bar instead: only a stranded
      // SINGLE word flags -- short multi-word tails are normal in long prose.
      const extremeOnly = generic || norm.length > cap;
      // Tokenise on \S+ (JS `\s` includes U+00A0, so `&nbsp;` is a SEPARATOR
      // here -- a glued pair is two tokens). Token COUNT no longer decides;
      // the WIDTH test below does. The recommended `&nbsp;` glue still helps,
      // by pulling the prior word down so the last line fills more of the
      // measure -- not by changing the token count.
      const toks = [];
      const re = /\S+/g;
      let m;
      while ((m = re.exec(para.flat)) !== null) {
        toks.push({s: m.index, e: m.index + m[0].length, t: m[0]});
      }
      // 0/1-word segment can't widow. Documented exception: a segment that is
      // ONLY display math plus one trailing word ("<mjx>...</mjx> one.") is
      // treated as a one-word paragraph, not a wrap -- same verdict as case
      // "Short." (the text never wrapped, so nothing was stranded BY a wrap).
      if (toks.length < 2) return;

      const rectsFor = (a, b) => {
        // PER-TEXT-NODE ranges: a single Range spanning from one text node to
        // another also returns the rects of any element BETWEEN its endpoints
        // -- for an unspaced "alpha<mjx/>beta" token that smuggles the tall
        // opaque rect in as a TEXT cell, poisoning the line-height median the
        // tolerance is built from. Measuring each text segment separately can
        // never cross an opaque subtree.
        const out = [];
        for (const sg of para.segs) {
          const sStart = sg.base, sEnd = sg.base + sg.text.length;
          const lo = Math.max(a, sStart), hi = Math.min(b, sEnd);
          if (lo >= hi) continue;
          const rng = document.createRange();
          rng.setStart(sg.node, lo - sStart);
          rng.setEnd(sg.node, hi - sStart);
          const rects = rng.getClientRects();
          for (let i = 0; i < rects.length; i++) out.push(rects[i]);
        }
        return out;
      };

      // Each VISIBLE rect becomes a line CELL carrying its token index, so a
      // long token that itself wraps across two lines (break-word / hyphenation)
      // contributes a cell to BOTH lines instead of collapsing the line model.
      const cells = [];                                       // {cy, h, ti, l, r}
      for (let ti = 0; ti < toks.length; ti++) {
        const rects = rectsFor(toks[ti].s, toks[ti].e);
        for (let i = 0; i < rects.length; i++) {
          const r = rects[i];
          if (r.width <= 0.5 || r.height <= 0.5) continue;    // drop zero-width wrap-space artefacts
          cells.push({cy: (r.top + r.bottom) / 2, h: r.height, ti: ti,
                      l: r.left, r: r.right});
        }
      }
      // Opaque cells (ti = -1): vote in line grouping, mark their line, but
      // never count as a "word". `media` distinguishes a figure/icon/table
      // (its last line stays unjudgeable) from inline math (judged with text).
      for (const op of para.ops) {
        const isMedia = !!(op.matches && op.matches(MEDIA));
        const rects = op.getClientRects();
        for (let i = 0; i < rects.length; i++) {
          const r = rects[i];
          if (r.width <= 0.5 || r.height <= 0.5) continue;
          cells.push({cy: (r.top + r.bottom) / 2, h: r.height, ti: -1,
                      l: r.left, r: r.right, media: isMedia});
        }
      }
      if (cells.length < 2) return;

      // Group cells into visual lines by center-y within a line-height
      // tolerance (NOT top +/- 2px: <sup>, mixed font-size and sub-pixel
      // rounding shift tops within one line). Each line keeps the SET of token
      // indices with a visible rect on it; the WIDTH test below judges the last
      // line (token count no longer decides).
      // Tolerance derives from TEXT cells only: tall opaque cells (display
      // math) would inflate the median height and merge a real text last line
      // into the line above, masking the widow.
      const hs = cells.filter(c => c.ti >= 0).map(c => c.h).sort((a, b) => a - b);
      const medH = hs.length ? hs[Math.floor((hs.length - 1) / 2)] : 0;
      const tol = Math.max(3, medH * 0.6);
      cells.sort((a, b) => a.cy - b.cy);
      const lines = [];
      let line = null;
      for (const c of cells) {
        if (line && (c.cy - line.cy) <= tol) {
          line.n += 1;
          line.cy += (c.cy - line.cy) / line.n;
        } else {
          line = {cy: c.cy, n: 1, tis: new Set(), op: false, media: false,
                  lo: Infinity, hi: -Infinity, flo: Infinity, fhi: -Infinity};
          lines.push(line);
        }
        // Only TEXT cells set the line's measured extent (`lo`/`hi`): an inline
        // opaque (display math / figure / table) wider than the prose must NOT
        // inflate the `measure` and make a normal text last line look like a
        // runt (Codex MAJOR). `flo`/`fhi` track the FULL visual extent (text +
        // opaque) and is used ONLY to size a text+math last line (case "by λ.").
        // Opaque cells still vote in grouping (via cy) above; `media` marks a
        // figure/icon/table line (kept unjudgeable), `op` marks any opaque.
        if (c.l < line.flo) line.flo = c.l;                   // full L/R extent
        if (c.r > line.fhi) line.fhi = c.r;                   // (text + opaque)
        if (c.ti >= 0) {
          line.tis.add(c.ti);
          if (c.l < line.lo) line.lo = c.l;                   // text L/R extent
          if (c.r > line.hi) line.hi = c.r;                   // of the visual line
        } else {
          line.op = true;
          if (c.media) line.media = true;
        }
      }
      if (lines.length < 2) return;                           // single visual line: nothing to widow
      // Census: this block genuinely WRAPS, so it either carries wrap
      // protection (text-wrap: pretty / balance) or it doesn't. Once per el.
      if (!censusCounted) {
        censusCounted = true;
        wrapCensus.push({
          cls: el.className || '', tag: el.tagName.toLowerCase(),
          protected: wrapProtected,
        });
      }
      const last = lines[lines.length - 1];
      // A last line carrying a FIGURE / icon / table (real media) is OUTSIDE
      // this prose-runt contract -- its width as a "runt" is meaningless and a
      // trailing inline icon may be deliberate, so it stays unjudgeable.
      if (last.media) return;
      // A last line carrying opaque content whose only text is PUNCTUATION
      // (a lone trailing equation/figure, optionally with a sentence period:
      // "$eq$." or "$eq$,") is intentional trailing content, not a stranded
      // word -- skip it. A real WORD on the line (a letter/digit token, e.g.
      // "by" in "by λ.") keeps the line judged.
      const lastHasWord = Array.from(last.tis)
        .some(ti => /[\p{L}\p{N}]/u.test(toks[ti].t));
      if (last.op && !lastHasWord) return;
      // Otherwise the last line is prose: pure text, OR text plus an inline
      // MATH symbol (mjx-container) that reads as part of the sentence. A short
      // tail ending in math ("traded off by $\\lambda$.") IS a stranded runt, so
      // we judge it by its FULL visual extent (text + math), not text alone --
      // the old blanket `if (last.op) return` hid exactly this case.
      // WIDTH-based runt test (replaces the old "exactly one token" rule). The
      // MEASURE is the widest typeset TEXT line (opaque widths excluded so an
      // inline figure can't inflate it); a last line filling less than
      // RUNT_FRAC of it is a stranded runt -- regardless of word COUNT. This
      // catches a SHORT two-word tail ("= OMAD-only.") the token rule missed,
      // and clears a SINGLE long word that fills the line (width ~= measure)
      // which the token rule wrongly flagged.
      const measure = Math.max(...lines.map(l => l.hi - l.lo));
      const lastW = last.fhi - last.flo;
      // The banner (.fb-text) must read as a FILLED rectangle, not merely avoid a
      // runt -- so it is judged against the higher BANNER_FILL_FRAC; all other
      // prose keeps the RUNT_FRAC runt bar. `closest` (not `matches`) so banner
      // text nested in a sub-candidate (.body-text/.caption inside .fb-text, which
      // would make the gate scan the child, not the .fb-text parent) still gets
      // the banner bar rather than silently falling back to the runt bar.
      const isBanner = !!el.closest('.fb-text');
      const threshold = isBanner ? BANNER_FILL_FRAC : RUNT_FRAC;
      // Conservative bar for long prose / generic blocks: judge ONLY a
      // stranded SINGLE word (one text token on the last line, still under
      // the runt width). Multi-word short tails are normal in long running
      // prose and unknowable in unlisted block types -- flagging them there
      // would flood; a lone stranded word is bad in ANY block type.
      if (extremeOnly && last.tis.size > 1) return;
      if (measure > 0 && (lastW / measure) < threshold) {
        const ord = Array.from(last.tis).sort((a, b) => a - b);
        widows.push({
          tag: el.tagName.toLowerCase(),
          cls: el.className || '',
          frac: Math.floor(lastW / measure * 100),   // floor: a flagged line never displays its own threshold %
          word: ord.map(ti => toks[ti].t).join(' ').slice(0, 40),
          lines: lines.length,
          text: (norm.length > 60) ? ('...' + norm.slice(-57)) : norm,
          banner: isBanner,   // banner -> "fill the rectangle" message; else the runt message
          mode: generic ? 'generic' : (extremeOnly ? 'long' : 'std'),
        });
      }
    });
  });

  // ---- 9) Framework-banner image slot ----
  // A captioned method figure in the optional framework banner whose flex
  // ITEM ("slot") is much wider than the image wastes banner width and steals
  // room from the body. Anchored on the IMG (not <figure>), so any wrapper
  // element the agent picks is covered. Deliberately NOT extended to the
  // `band` role: the shipped banner-figure contract makes "slot = banner's
  // direct child" meaningful, but a custom band usually wraps its whole
  // content in one inner element -- the walk-up would call the full band
  // the "slot" and flag a legitimate image-beside-text layout. Bands get
  // the hero-style letterbox + broken checks instead (section 1). The "slot" is the banner's DIRECT
  // child that contains the image -- the box that competes with the body for
  // banner width; a bare <img> child IS its own slot, so slack==0 and it can
  // never trip. `caption_like_w` is the widest non-image descendant of the
  // slot (the caption/text block that may be setting the slot width).
  const bannerImgs = [];
  document.querySelectorAll('[data-measure-role="banner"]').forEach(banner => {
    const br = banner.getBoundingClientRect();
    banner.querySelectorAll('img').forEach(img => {
      const ir = img.getBoundingClientRect();
      if (ir.width <= 0 || ir.height <= 0) return;
      // Walk up to the banner's direct child (the flex/grid item). If the img
      // is itself a direct child of the banner, slot === img.
      let slot = img, p = img.parentElement;
      while (p && p !== banner) { slot = p; p = p.parentElement; }
      if (p !== banner) return;  // img not actually under this banner
      const sr = slot.getBoundingClientRect();
      // Widest non-image content in the slot = the caption/text block. Exclude
      // the img and any element that CONTAINS it (those are slot-wide by
      // construction and would mask the signal).
      let captionLikeW = 0;
      slot.querySelectorAll('*').forEach(el => {
        if (el === img || el.contains(img)) return;
        const r = el.getBoundingClientRect();
        if (r.height > 0 && r.width > captionLikeW) captionLikeW = r.width;
      });
      // A caption written as BARE text directly in the slot (no <figcaption>)
      // is invisible to the element scan but can still expand the slot. Measure
      // text-run rects too and keep the widest.
      const tw = document.createTreeWalker(slot, NodeFilter.SHOW_TEXT);
      for (let tn = tw.nextNode(); tn; tn = tw.nextNode()) {
        if (!tn.nodeValue || !tn.nodeValue.trim()) continue;
        const rng = document.createRange();
        rng.selectNodeContents(tn);
        const rects = rng.getClientRects();
        for (let i = 0; i < rects.length; i++) {
          if (rects[i].height > 0 && rects[i].width > captionLikeW) {
            captionLikeW = rects[i].width;
          }
        }
      }
      bannerImgs.push({
        src: img.getAttribute('src') || '',
        obj_fit: window.getComputedStyle(img).objectFit || '',
        banner_w: br.width,
        slot_w: sr.width,
        slot_is_img: slot === img,
        off_left: ir.left - sr.left,
        off_right: sr.right - ir.right,
        rendered_w: ir.width,
        rendered_h: ir.height,
        natural_w: img.naturalWidth || 0,
        natural_h: img.naturalHeight || 0,
        caption_like_w: captionLikeW,
      });
    });
  });

  // ---- 7) Inner-card void: oversized gap BETWEEN a card's stacked
  //         children ----
  // SPACE-BETWEEN catches a gap BETWEEN cards in a column; CARD/TRAILING
  // catches blank BELOW a card's last line. Neither sees a void in the
  // MIDDLE of a card -- e.g. a `.card` stretched to an equal-height grid
  // row taller than its content with a child pinned to the bottom
  // (`margin-top: auto`, or `justify-content: space-*` on the card). The
  // slack opens below the last real block and above the pinned one, so
  // trailing reads ~0. Measured purely by geometry (largest inter-child
  // vertical gap minus the stated row-gap) so the mechanism does not
  // matter, and scoped to `.card` (not just data-measure-role) so an
  // agent-authored feature band whose cards aren't tagged is still seen.
  const innerVoids = [];
  const seenIV = new Set();
  // Scope to the poster so a stray `.card` outside it can't be sampled.
  const ivRoot = document.querySelector('[data-measure-role="poster"]')
              || document;
  // Shared geometry: largest inter-child vertical gap inside `box`, minus its
  // stated row-gap. Used for cards AND for header/footer tracks below.
  // A positioned child may veto a void band only when it is wide, VISIBLE,
  // and actually carries something -- paint (background), media, or real
  // text. An invisible/empty positioned box must not mask a real void.
  // `visibleIn` closes the invisibility channels innerText alone misses:
  // opacity:0 / transparent ink anywhere on the chain up to the veto box.
  const visibleIn = (el, root) => {
    for (let e = el; e && e !== root.parentElement; e = e.parentElement) {
      const es = window.getComputedStyle(e);
      if (es.display === 'none' || es.visibility === 'hidden'
          || es.visibility === 'collapse'
          || parseFloat(es.opacity) === 0) {
        return false;
      }
    }
    return true;
  };
  // Alpha of a computed color string: comma-syntax rgba(...) OR slash
  // alpha in any modern space (oklch(.5 .1 20 / 0), color(srgb 0 0 0 / 4%)).
  // No alpha channel present -> opaque (1).
  const alphaOfColor = (str) => {
    let m = /rgba\([^)]*,\s*([\d.]+)\)/.exec(str || '');
    if (m) return parseFloat(m[1]);
    m = /\/\s*([\d.]+%?)\s*\)/.exec(str || '');
    if (m) {
      return m[1].endsWith('%')
        ? parseFloat(m[1]) / 100 : parseFloat(m[1]);
    }
    return 1;
  };
  const absSubstantive = (c, contW) => {
    const r = c.getBoundingClientRect();
    if (r.height <= 0 || r.width < 0.5 * contW) return false;
    // The veto element itself gets the full invisibility test (display /
    // hidden / collapse / opacity) -- single hop of the same chain walk.
    if (!visibleIn(c, c)) return false;
    const cs2 = window.getComputedStyle(c);
    // Painted fill = background only, judged by parsed ALPHA -- a fully
    // transparent rgba(255, 0, 0, 0) or oklch(... / 0) paints nothing. A
    // 1px border is decoration, not a band fill, and must not veto.
    const bg = cs2.backgroundColor || '';
    if ((bg && bg !== 'transparent' && alphaOfColor(bg) >= 0.05)
        || (cs2.backgroundImage && cs2.backgroundImage !== 'none')) {
      return true;
    }
    // VISIBLE ink with some substance -- hidden/opacity:0/transparent text
    // or a lone glyph in a big empty box must not veto the band.
    let inkLen = 0;
    const twv = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    for (let tn = twv.nextNode(); tn; tn = twv.nextNode()) {
      const frag = (tn.nodeValue || '').trim();
      if (!frag) continue;
      const pe = tn.parentElement;
      if (!pe || !visibleIn(pe, c)) continue;
      const pc = window.getComputedStyle(pe).color || '';
      if (alphaOfColor(pc) < 0.05) continue;   // transparent ink
      inkLen += frag.length;
      if (inkLen >= 8) return true;
    }
    // Media: the element ITSELF, or a VISIBLE descendant that fills a real
    // share of the box (a tiny icon in a big empty container doesn't).
    const MEDIA_SEL = 'img, svg, canvas, video';
    if (c.matches && c.matches(MEDIA_SEL)) return true;
    for (const m of c.querySelectorAll(MEDIA_SEL)) {
      const mr = m.getBoundingClientRect();
      if (mr.height >= 0.3 * r.height && mr.width > 0
          && visibleIn(m, c)) {
        return true;
      }
    }
    // Accepted residual: a container with real VISIBLE text/media still
    // vetoes by its whole bbox even when the content sits in one corner --
    // this is a soft, waivable warning and the veto errs toward silence.
    return false;
  };
  const interChildVoid = (box, extraAbs) => {
    const cs = window.getComputedStyle(box);
    const cr = box.getBoundingClientRect();
    if (cr.height <= 0) return null;
    const gap = parseFloat(cs.rowGap || cs.gap || '0') || 0;
    // Direct, in-flow element children with a real box. Skip abs/fixed
    // (a corner badge/QR is not flow content). Use getAttribute('class')
    // -- an SVG child's `.className` is an SVGAnimatedString and .trim()
    // on it throws, which would crash the whole evaluate.
    const all = Array.from(box.children).map(c => {
      const r = c.getBoundingClientRect();
      const pos = window.getComputedStyle(c).position;
      const cl = ((c.getAttribute('class') || '').trim()
                    .split(/\s+/)[0]) || '';
      return {tag: c.tagName.toLowerCase(), cls: cl, top: r.top,
              bottom: r.bottom, h: r.height, w: r.width, pos};
    });
    const kids = all
      .filter(c => c.h > 0 && c.pos !== 'absolute' && c.pos !== 'fixed')
      .sort((a, b) => a.top - b.top);
    if (kids.length < 2) return null;
    // Absolutely-positioned children are NOT flow content (a corner badge
    // must not mask a void above it) -- but a SUBSTANTIVE positioned child
    // that genuinely covers a candidate band (a full-width positioned
    // figure) is not blank space either. Wide, VISIBLE, non-empty abs
    // boxes get to veto a band (extraAbs carries boxes from unwrapped
    // wrapper levels -- see the track loop).
    const absKids = (extraAbs || []).concat(
      Array.from(box.children).filter(c => {
        const pos = window.getComputedStyle(c).position;
        return pos === 'absolute' || pos === 'fixed';
      }).filter(c => absSubstantive(c, cr.width))
        .map(c => { const r = c.getBoundingClientRect();
                    return {top: r.top, bottom: r.bottom}; }));
    // Merge same-row children: walk in top order tracking the running MAX
    // bottom of everything seen so far, and count a gap only when a child
    // STARTS below that max. A side-by-side row (figure beside text, a
    // flex row) is dominated by its tallest member, so a following block
    // that clears the tall one is NOT a void -- this avoids measuring
    // `next.top - shortSibling.bottom` across an already-filled row.
    // NOTE: only DIRECT children are inspected; a void nested inside a
    // single wrapper (`.card > .body` flex column) is not seen -- keep a
    // card's content flat for the gate to cover it (see SKILL.md Gate C).
    let rowMaxBottom = kids[0].bottom;
    let rowMaxIdx = 0;
    const bands = [];
    for (let i = 1; i < kids.length; i++) {
      const g = kids[i].top - rowMaxBottom;
      if (g > 0) {
        bands.push({g, top: rowMaxBottom, bottom: kids[i].top,
                    above: rowMaxIdx, below: i});
      }
      if (kids[i].bottom > rowMaxBottom) {
        rowMaxBottom = kids[i].bottom;
        rowMaxIdx = i;
      }
    }
    // Largest band no flow child covers, skipping bands a wide positioned
    // child fills (>= 60% of the band's height).
    const absCover = (band) => {
      let best = 0;
      for (const a of absKids) {
        const ov = Math.min(a.bottom, band.bottom)
                 - Math.max(a.top, band.top);
        if (ov > best) best = ov;
      }
      return best / (band.bottom - band.top);
    };
    let maxGap = 0, pairBelow = -1, pairAbove = -1;
    for (const b of bands) {
      if (b.g <= maxGap) continue;
      if (absCover(b) >= 0.6) continue;
      maxGap = b.g; pairAbove = b.above; pairBelow = b.below;
    }
    const lab = k => k.tag + (k.cls ? '.' + k.cls : '');
    return {
      h: cr.height,
      stated_gap: gap,
      excess: maxGap - gap,
      above: pairAbove >= 0 ? lab(kids[pairAbove]) : '',
      below: pairBelow > 0 ? lab(kids[pairBelow]) : '',
    };
  };
  ivRoot.querySelectorAll('.card, [data-measure-role="card"]')
    .forEach(card => {
      if (seenIV.has(card)) return;
      seenIV.add(card);
      const v = interChildVoid(card);
      if (!v) return;
      innerVoids.push({
        cls: (card.getAttribute('class') || ''),
        card_h: v.h,
        stated_gap: v.stated_gap,
        excess: v.excess,
        above: v.above,
        below: v.below,
      });
    });

  // ---- 7b) Track void: the same stacked-children void inside a HEADER /
  //          FOOTER track (a vertical masthead spine, a side rail). These
  //          tracks are neither measure columns nor `.card`s, so every void
  //          gate above is blind there -- a wave-2 poster stretched its
  //          full-height title spine with `justify-content: space-between`
  //          and shipped two ~500 px voids, all gates green. What it
  //          measures is the largest vertical band NO child covers -- so a
  //          height-aligned horizontal masthead row stays quiet (children
  //          overlap vertically), while side-by-side columns that are
  //          vertically OFFSET (one hugging the top, one the bottom) do
  //          register: the uncovered band between them is a real void.
  const trackVoids = [];
  ivRoot.querySelectorAll(
      '[data-measure-role="header"], [data-measure-role="footer"]')
    .forEach(track => {
      if (seenIV.has(track)) return;
      seenIV.add(track);
      // Unwrap single-child padding/layout wrappers (header > .inner with
      // the space-between on .inner): the void walk inspects DIRECT
      // children only, and a lone wrapper used to hide the whole track.
      let box = track;
      const outerAbs = [];
      const trackW = track.getBoundingClientRect().width;
      for (let hops = 0; hops < 4; hops++) {
        // A substantive positioned child at THIS level still covers bands
        // measured after unwrapping -- carry it along (review round 3:
        // wrapper + outer positioned figure combined used to false-flag).
        Array.from(box.children).forEach(c => {
          const pos = window.getComputedStyle(c).position;
          if ((pos === 'absolute' || pos === 'fixed')
              && absSubstantive(c, trackW)) {
            const r = c.getBoundingClientRect();
            outerAbs.push({top: r.top, bottom: r.bottom});
          }
        });
        const flow = Array.from(box.children).filter(c => {
          const r = c.getBoundingClientRect();
          const pos = window.getComputedStyle(c).position;
          return r.height > 0 && pos !== 'absolute' && pos !== 'fixed';
        });
        if (flow.length !== 1) break;
        box = flow[0];
      }
      const v = interChildVoid(box, outerAbs);
      if (!v) return;
      trackVoids.push({
        role: track.getAttribute('data-measure-role') || '',
        cls: (track.getAttribute('class') || ''),
        track_h: v.h,
        stated_gap: v.stated_gap,
        excess: v.excess,
        above: v.above,
        below: v.below,
        space_between: (window.getComputedStyle(box).justifyContent || '')
          .indexOf('space') !== -1,
      });
    });

  // ---- 10) Composed text/ground contrast ----
  // style_check verifies DECLARED token pairs; nothing verified the COMPOSED
  // result -- an emphasis span inheriting white text while its own class
  // paints a pale highlight behind it (wave-2: white '4.05' on #CFE6E4,
  // 1.4:1), or an emph-colored lead-in on an accent fill (wave-1: rust on
  // steel blue, 1.2:1). Sample the RENDERED foreground of every text run
  // against the effective ground beneath it: the hit-test stack under the
  // sample point, alpha-composited until opaque. Text over images/gradients
  // (or any replaced layer) is unjudgeable and skipped -- this is a
  // solid-fill contract; verify those grounds on the rendered crop.
  const contrasts = [];
  {
    const parseC = (s) => {
      const m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/
        .exec(s || '');
      if (!m) return null;
      return {r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4]};
    };
    const over = (top, bot) => {         // source-over compositing
      const a = top.a + bot.a * (1 - top.a);
      if (a <= 0) return {r: 0, g: 0, b: 0, a: 0};
      return {
        r: (top.r * top.a + bot.r * bot.a * (1 - top.a)) / a,
        g: (top.g * top.a + bot.g * bot.a * (1 - top.a)) / a,
        b: (top.b * top.a + bot.b * bot.a * (1 - top.a)) / a,
        a,
      };
    };
    const lum = (c) => {
      const f = (v) => {
        v /= 255;
        return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
      };
      return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
    };
    const ratioOf = (c1, c2) => {
      const l1 = lum(c1), l2 = lum(c2);
      return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    };
    const hex = (c) => '#' + [c.r, c.g, c.b]
      .map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
    const REPLACED_RE = /^(IMG|CANVAS|VIDEO|SVG|IFRAME|OBJECT|EMBED)$/;
    // Effective ground beneath `el` at (x, y): walk the hit-test stack from
    // el downward, compositing translucent fills until one is opaque.
    // null = unjudgeable (image/gradient/replaced layer, or el not hit).
    const groundAt = (el, x, y) => {
      // elementsFromPoint only resolves INSIDE the layout viewport; the
      // render pipeline sets the viewport to the full poster canvas, so
      // every on-canvas glyph is reachable -- text overflowing the canvas
      // (already a hard `measure` failure) silently skips instead.
      const stack = document.elementsFromPoint(x, y);
      const idx = stack.indexOf(el);
      if (idx === -1) return null;         // covered oddly / pointer-events
      let acc = null;                      // accumulated translucent paint
      for (let i = idx; i < stack.length; i++) {
        const layer = stack[i];
        if (layer !== el && REPLACED_RE.test(layer.tagName.toUpperCase())) {
          return null;                     // picture ground: unjudgeable
        }
        const ls = window.getComputedStyle(layer);
        if (ls.backgroundImage && ls.backgroundImage !== 'none') return null;
        // A painted ::before/::after is invisible to elementsFromPoint (its
        // paint belongs to the originating element), so a pseudo-element
        // fill -- e.g. a split two-tone header band drawn by
        // `.header::before/::after` -- would silently read as whatever sits
        // BELOW it (white-on-white false positives, wave-2 poster 4). A
        // layer carrying a painted pseudo makes the ground unjudgeable.
        for (const pe of ['::before', '::after']) {
          const ps = window.getComputedStyle(layer, pe);
          if (ps.content === 'none') continue;
          const pRaw = ps.backgroundColor || '';
          const pBc = parseC(pRaw);
          // Same contract as real layers: a painted pseudo OR one whose
          // color the parser can't read (oklch()/lab()) is unjudgeable --
          // treating a parse failure as alpha 0 would see THROUGH the fill.
          if ((ps.backgroundImage && ps.backgroundImage !== 'none')
              || (pBc ? pBc.a > 0 : (pRaw && pRaw !== 'transparent'))) {
            return null;
          }
        }
        // A translucent layer (opacity < 1 on the element or any ancestor
        // in the stack) changes the effective ink/ground in ways this flat
        // model doesn't composite -- unjudgeable.
        if (parseFloat(ls.opacity) < 1) return null;
        const rawBc = ls.backgroundColor || '';
        const bc = parseC(rawBc);
        if (!bc) {
          // An authored color the parser can't read (oklch()/lab()/color())
          // must be unjudgeable, NOT silently transparent -- falling through
          // would judge against whatever paint sits below it.
          if (rawBc && rawBc !== 'transparent') return null;
          continue;
        }
        if (bc.a <= 0) continue;
        acc = acc ? over(acc, bc) : bc;
        if (acc.a >= 0.999) return acc;
      }
      // Fell through every layer: composite over the canvas default (white).
      const white = {r: 255, g: 255, b: 255, a: 1};
      return acc ? over(acc, white) : white;
    };
    const seenCEls = new Set();
    // Aggregate JS-side by (class | fg | bg), keeping the WORST ratio per
    // combo: a fixed collection cap in DOM order could otherwise fill up on
    // early borderline runs and silently drop a severe defect further down
    // the document. Unique low-contrast combos are bounded by the stylesheet
    // (dozens), so the map stays small; 300 is a runaway backstop.
    const contrastMap = new Map();
    const cRoot = document.querySelector('[data-measure-role="poster"]')
               || document.body;
    const ctw = document.createTreeWalker(cRoot, NodeFilter.SHOW_TEXT);
    for (let tn = ctw.nextNode(); tn; tn = ctw.nextNode()) {
      if (!/\S/.test(tn.nodeValue || '')) continue;
      const el = tn.parentElement;
      if (!el || seenCEls.has(el)) continue;
      seenCEls.add(el);
      if (el.closest('mjx-container, .MathJax, math, svg, script, style')) {
        continue;                          // math/vector ink: out of scope
      }
      const cs = window.getComputedStyle(el);
      if (cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
      // Outlined / shadowed text has engineered edge contrast this flat-fill
      // model can't score -- skip rather than mis-judge.
      if (cs.textShadow && cs.textShadow !== 'none') continue;
      if (parseFloat(cs.webkitTextStrokeWidth) > 0) continue;
      const fg0 = parseC(cs.color);
      // Unparsable foreground (oklch()/lab() ink) is DELIBERATELY skipped
      // as unjudgeable -- same contract as grounds; token-disciplined
      // posters author hex/rgb (SKILL.md Gate G limits).
      if (!fg0 || fg0.a < 0.05) continue;
      // Sample the first and last glyph runs of this text node -- a run
      // crossing two fills is judged at both ends, worst sample wins.
      const rng = document.createRange();
      rng.selectNodeContents(tn);
      const rects = Array.from(rng.getClientRects())
        .filter(r => r.width > 1 && r.height > 1);
      if (!rects.length) continue;
      const pts = [rects[0], rects[rects.length - 1]]
        .map(r => [(r.left + r.right) / 2, (r.top + r.bottom) / 2]);
      let worst = null;
      for (const p of pts) {
        const g = groundAt(el, p[0], p[1]);
        if (!g) continue;
        const fg = fg0.a < 1 ? over(fg0, g) : fg0;
        const rr = ratioOf(fg, g);
        if (!worst || rr < worst.ratio) worst = {ratio: rr, ground: g, fg};
      }
      // Only sub-7.0 samples ship to Python (payload stays small; the WARN
      // threshold itself lives Python-side as --min-contrast, so any floor
      // up to 7.0 is fully served -- higher floors are not supported).
      if (!worst || worst.ratio >= 7.0) continue;
      const fgHex = hex(worst.fg), bgHex = hex(worst.ground);
      const key = (el.className || '') + '|' + fgHex + '|' + bgHex;
      const prev = contrastMap.get(key);
      if (prev) {
        prev.count += 1;
        if (worst.ratio < prev.ratio) {
          prev.ratio = Math.round(worst.ratio * 100) / 100;
          prev.text = (tn.nodeValue || '')
            .replace(/\s+/g, ' ').trim().slice(0, 32);
        }
      } else {
        if (contrastMap.size >= 300) {
          // Backstop full: keep the map biased toward the WORST pairs, not
          // toward DOM order -- evict the highest-ratio combo if this one
          // is lower; drop it otherwise.
          let maxKey = null, maxRatio = -1;
          contrastMap.forEach((v, k) => {
            if (v.ratio > maxRatio) { maxRatio = v.ratio; maxKey = k; }
          });
          if (worst.ratio >= maxRatio) continue;
          contrastMap.delete(maxKey);
        }
        contrastMap.set(key, {
          tag: el.tagName.toLowerCase(),
          cls: el.className || '',
          text: (tn.nodeValue || '').replace(/\s+/g, ' ').trim().slice(0, 32),
          fg: fgHex,
          bg: bgHex,
          ratio: Math.round(worst.ratio * 100) / 100,
          px: Math.round(parseFloat(cs.fontSize) || 0),
          count: 1,
        });
      }
    }
    contrastMap.forEach(v => contrasts.push(v));
  }

  return {figures, orphans, cols, cards, innerVoids, trackVoids, flexbr,
          besideVoids, widows, glueChains, wrapCensus, contrasts,
          logos, qrs, header_w: headerW, header_h: headerH,
          header_cx: headerCx,
          header_content_left: headerContentLeft,
          header_content_right: headerContentRight,
          header_content_top: headerContentTop,
          header_content_bottom: headerContentBottom, headerBlocks,
          bannerImgs};
}
"""


def collect_polish_data(page):
    """Run the polish measurement JS on an already-open, already-settled
    page and return the raw result dict.

    Split out of :func:`cmd_polish` so the same measurement can ride a
    SHARED rendered page (``measure --with-polish``) instead of paying a
    second Chromium launch. Pure read-only DOM geometry -- it mutates
    nothing, so running it after another gate's probes on the same page
    yields identical numbers.
    """
    return page.evaluate(_POLISH_JS)


def default_polish_args() -> argparse.Namespace:
    """Polish gate thresholds at their CLI defaults, for callers that run
    the gates without owning a polish arg namespace (``measure
    --with-polish``). Only the attrs :func:`report_polish` reads
    directly are set; everything else is read defensively via getattr
    with the same DEFAULT_* constants. ``strict`` stays False -- the
    merged path is advisory by design.
    """
    return argparse.Namespace(
        wide_min_ratio=DEFAULT_WIDE_MIN_RATIO,
        tall_max_ratio=DEFAULT_TALL_MAX_RATIO,
        square_min_ratio=DEFAULT_SQUARE_MIN_RATIO,
        max_space_between_fill=DEFAULT_MAX_SPACE_BETWEEN_FILL,
        max_card_trailing=DEFAULT_MAX_CARD_TRAILING,
        strict=False,
    )


def advisory_polish_on_page(page, html_path: Path) -> None:
    """Best-effort polish pass on a page some other gate already rendered
    and settled (``measure --with-polish``). Advisory only: prints the
    polish report at default thresholds, never raises, never changes the
    caller's exit code. Skipped (with a note) when the poster lacks the
    measure-role markup polish requires, or if the measurement itself
    fails -- a broken advisory pass must not break the hard gate.
    """
    try:
        role_counts = _preflight.has_required_roles_in_html(html_path)
        missing = [r for r in ("poster", "card", "column")
                   if role_counts.get(r, 0) == 0]
        if missing:
            _eprint(
                f"[measure] --with-polish: skipping polish pass, poster "
                f"is missing measure-role markup {missing}"
            )
            return
        data = collect_polish_data(page)
    except Exception as e:
        _eprint(
            f"[measure] --with-polish: polish measurement failed, "
            f"skipped ({e})"
        )
        return
    print("[measure] --with-polish advisory report (same rendered page; "
          "never gates measure's exit):")
    try:
        report_polish(data, default_polish_args(), html_path)
    except Exception as e:
        _eprint(f"[measure] --with-polish: polish report failed ({e})")


def cmd_polish(args: argparse.Namespace) -> int:
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

    # Hard-fail if there's no measurement markup at all. A polish PASS
    # on "0 figures, 0 columns, 0 stat-like elements" would be silent
    # success on a file the tool can't reason about.
    role_counts = _preflight.has_required_roles_in_html(html_path)
    must_have = ("poster", "card", "column")
    missing = [r for r in must_have if role_counts.get(r, 0) == 0]
    if missing:
        _eprint(
            f"ERROR: polish requires data-measure-role markup on the "
            f"poster, columns, and cards. Missing or zero-count: "
            f"{missing}. Either add the roles or use a different tool."
        )
        return 2

    resolved = _canvas.resolve_canvas(
        html_path, args.canvas, label="[polish]"
    )
    if resolved is None:
        _eprint(
            "ERROR: could not find `@page { size: <W> <H> }` in HTML; "
            "pass `--canvas <W>x<H>in` or `--canvas 'A0 portrait'`."
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
            # otherwise fail-fast below. polish must NOT sample a poster
            # that never finished loading -- a blocked remote image or web
            # font would otherwise sneak through as a false PASS.
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
                f"{args.mathjax_timeout_ms} ms; refusing to polish a "
                "partially loaded poster. A blocked/slow remote resource "
                "(CDN image, web font, MathJax) is the usual cause -- "
                "inline assets, or raise --mathjax-timeout-ms."
            )
            return 1

        data = collect_polish_data(page)
        browser.close()

    return report_polish(data, args, html_path)


def report_polish(data: dict, args: argparse.Namespace,
                  html_path: Path) -> int:
    """Apply the visual-polish gates (A-F) to data gathered by
    :func:`collect_polish_data` and print the report. Page-free, so the
    same reporting runs for standalone ``polish`` and for the merged
    ``measure --with-polish`` path (which shares one rendered page).
    Returns the process exit code (1 only under ``args.strict`` with
    warnings present).
    """
    warns: list[str] = []

    # ---- Gate A: figure sizing by AR ----
    # Read defensively: programmatic callers / tests build a Namespace
    # directly and may predate this flag (mirrors measure.py's fallback
    # style for newly added args).
    tall_min = getattr(args, "tall_min_ratio", DEFAULT_TALL_MIN_RATIO)
    hero_fill = getattr(
        args, "hero_letterbox_fill", DEFAULT_HERO_LETTERBOX_FILL)
    hero_ar_mult = getattr(
        args, "hero_letterbox_ar_mult", DEFAULT_HERO_LETTERBOX_AR_MULT)
    for f in data.get("figures", []):
        rw = float(f["rendered_w"])
        rh = float(f.get("rendered_h", 0.0))
        cw = float(f["card_w"])
        nw = float(f["natural_w"])
        nh = float(f["natural_h"])
        role = f.get("role", "card")
        src_l = str(f["src"]).lower()
        # A vector image (SVG) can legitimately report zero natural size
        # while rendering fine, so never flag it broken. Match the path
        # extension (after stripping any ?query / #fragment) plus inline
        # SVG data URIs. Imperfect: an SVG behind an extensionless URL
        # still slips through; an `img.decode()`-based JS probe would be
        # exact. Covers both card and hero <img> (see _POLISH_JS).
        src_path = src_l.split("?", 1)[0].split("#", 1)[0]
        is_svg = (
            src_path.endswith((".svg", ".svgz"))
            or src_l.startswith("data:image/svg")
        )
        if (nw <= 0 or nh <= 0) and not is_svg:
            warns.append(
                f"FIG/BROKEN: '{ascii_safe(f['src'])}' has zero natural "
                "size -- the image failed to load (missing file, 404, or "
                "an unreachable remote URL); it will be blank in print."
            )
            continue
        # Hero figures: the %-of-card-width AR gates below don't apply (a
        # hero panel has no card budget), but a hero image is NOT
        # automatically fine -- the HERO/STAGE-LETTERBOX check after
        # content_w is computed catches a narrow picture stranded in a
        # wide-short stage. (Old code blanket-skipped role=="hero" here.)
        if cw <= 0 or rw <= 0:
            continue
        # AR from natural size when available. An SVG (or any figure that
        # reported zero natural size yet rendered) falls back to its
        # RENDERED aspect ratio so the sizing gates still apply -- the
        # skill recommends converting vector figures to SVG, and a
        # zero-natural SVG would otherwise slip every AR gate below.
        if nw > 0 and nh > 0:
            ar = nw / nh
        elif rh > 0:
            ar = rw / rh
        else:
            continue
        # Rendered PICTURE width inside the <img> box. `object-fit` decides how
        # the bitmap fills the element box; only contain/scale-down/none can
        # leave left+right voids INSIDE a (often full-width) box, which the old
        # element-box `ratio` missed. Compute the visible picture width so both
        # the AR gates AND the beside-text centring test below judge what
        # actually prints, not the element box:
        #   contain     : scale to fit            -> min(box_w, box_h*AR)
        #   scale-down  : contain but never upscale past natural -> clamp by nw
        #   none        : natural size, box-clipped -> min(box_w, nw)
        #   fill/cover/'': fill the box width      -> box_w
        obj_fit = str(f.get("obj_fit", "")).strip().lower()
        if obj_fit in ("contain", "scale-down") and rh > 0 and ar > 0:
            content_w = min(rw, rh * ar)
            if obj_fit == "scale-down" and nw > 0:
                content_w = min(content_w, float(nw))
        elif obj_fit == "none" and nw > 0:
            content_w = min(rw, float(nw))
        else:
            content_w = rw
        # Hero/band branch: stop blanket-exempting hero images. The
        # %-of-card AR gates don't fit a hero panel or a full-width band,
        # but a narrow-aspect picture dropped into a wide-but-SHORT stage
        # is height-constrained and leaves big symmetric side voids. Flag
        # exactly that shape (same geometry for both roles).
        if role in ("hero", "band"):
            sw = float(f.get("stage_w", 0) or 0)
            sh = float(f.get("stage_h", 0) or 0)
            ol = f.get("off_left")
            orr = f.get("off_right")
            if sw > 0 and sh > 0 and ol is not None and orr is not None:
                fill = content_w / sw
                stage_ar = sw / sh
                ar_mult = (stage_ar / ar) if ar > 0 else 0.0
                # Side void = the img's offset within the stage PLUS half the
                # internal object-fit letterbox, so a hero img sized
                # width/height:100% with object-fit:contain (element box fills
                # the stage, picture letterboxed inside) is judged on the
                # visible PICTURE, not the element box. Mirrors the card
                # beside-text centring test.
                void = max(0.0, rw - content_w)
                pic_left = float(ol) + void / 2.0
                pic_right = float(orr) + void / 2.0
                symmetric = (min(pic_left, pic_right) > 0.15 * sw
                             and abs(pic_left - pic_right) < 0.12 * sw)
                if (fill < hero_fill and ar_mult > hero_ar_mult
                        and symmetric):
                    warns.append(
                        f"{role.upper()}/STAGE-LETTERBOX: "
                        f"'{ascii_safe(f['src'])}' "
                        f"(AR={ar:.2f}) fills only {fill * 100:.0f}% of its "
                        f"{role}-stage width -- the stage is "
                        f"{stage_ar:.1f}:1, "
                        f"much wider than the image, so a height-constrained "
                        f"picture leaves big symmetric side voids. Give the "
                        f"figure real vertical room (move a secondary diagram "
                        f"out of the {role} into a card), or constrain the "
                        f"stage width toward the image's aspect ratio."
                    )
            continue
        # Author opt-out for a DELIBERATE image-left/text-right card: a figure
        # that shares its card with a real side-by-side / float-wrapped text
        # column is sized below the AR thresholds on purpose. Marking the <img>
        # `data-fig-layout="beside-text"` records that intent so a later edit
        # leaves the layout alone instead of widening to silence the warning.
        # It skips only the AR width gates; the FIG/BROKEN check above still
        # applies. The documented MISUSE is a CENTRED, text-less small figure
        # tagged just to mute the warning (SKILL.md: "not a generic mute").
        # Detect it on the visible PICTURE -- element offsets PLUS half the
        # internal letterbox void, so a full-width object-fit:contain image
        # tagged beside-text can't hide a centred picture behind a full-width
        # box: symmetric side voids => centred => fall through and warn; hugged
        # to one side => honour. Offsets absent (programmatic/test callers) =>
        # honour as before. NOTE: this proves the picture sits to one side, not
        # that text actually fills the other -- a side-hugged text-less figure
        # is still honoured (accepted residual; the documented misuse is the
        # centred one).
        if str(f.get("fig_layout", "")).strip() == "beside-text":
            ol = f.get("off_left")
            orr = f.get("off_right")
            if ol is None or orr is None:
                continue
            void = max(0.0, rw - content_w)
            pic_left = float(ol) + void / 2.0
            pic_right = float(orr) + void / 2.0
            centred = (min(pic_left, pic_right) > 0.08 * cw
                       and abs(pic_left - pic_right) < 0.12 * cw)
            if not centred:
                continue
            # centred-with-side-voids: opt-out misused, do not skip.
        ratio = content_w / cw
        if ar > 1.3 and ratio < args.wide_min_ratio:
            warns.append(
                f"FIG/WIDE: '{ascii_safe(f['src'])}' (AR={ar:.2f}) at "
                f"{ratio * 100:.0f}% of card width -- "
                f"{args.wide_min_ratio * 100:.0f}% is the defect FLOOR, "
                f"not the target: a figure that owns its card reads "
                f"best at 90-100% width (field-calibrated -- 70%-era "
                f"floors still shipped visible small-stamp cards). "
                f"Enlarge, or drop the image-left/text-right wrapper."
            )
        elif ar < 0.8 and ratio > args.tall_max_ratio:
            warns.append(
                f"FIG/TALL: '{ascii_safe(f['src'])}' (AR={ar:.2f}) at "
                f"{ratio * 100:.0f}% of card width -- a tall figure this "
                f"wide gets awkward; shrink to 45-60%, or use a verified "
                f"float/beside-text wrap layout."
            )
        elif ar < 0.8 and ratio < tall_min:
            warns.append(
                f"FIG/TALL-SMALL: '{ascii_safe(f['src'])}' (AR={ar:.2f}) at "
                f"{ratio * 100:.0f}% of card width -- a tall figure this "
                f"narrow renders small with wide side margins. Enlarge "
                f"toward 45-60%, or wrap text around it with a verified "
                f"float/beside-text layout. If the small size is genuinely "
                f"intended, this is a soft WARN you can accept."
            )
        elif 0.8 <= ar <= 1.3 and ratio < args.square_min_ratio:
            warns.append(
                f"FIG/SQUARE: '{ascii_safe(f['src'])}' (AR={ar:.2f}) at "
                f"{ratio * 100:.0f}% of card width -- square figures "
                f"sit better at {args.square_min_ratio * 100:.0f}-75%."
            )

    # ---- Gate A2: beside-text float void ----
    # A figure floated beside text whose wrapping text stops short of the
    # figure bottom leaves an L-shaped void below the text. The beside-text
    # AR opt-out above only proved the figure is side-hugged (not a centred
    # mis-tag); it never checked the text fills the other side. This closes
    # that residual. deficit = how far the text falls short of the figure
    # bottom; text flowing PAST the figure yields a non-positive deficit
    # (no warn). The 1.5-line guard avoids flagging a sub-line shortfall.
    beside_void = getattr(
        args, "beside_void_ratio", DEFAULT_BESIDE_VOID_RATIO)
    for bv in data.get("besideVoids", []):
        fig_h = float(bv.get("fig_h", 0) or 0)
        if fig_h <= 0:
            continue
        tb = bv.get("text_bottom")
        if tb is None:
            warns.append(
                f"FIG/BESIDE-TEXT-VOID: '{ascii_safe(bv.get('src', ''))}' "
                f"floats beside text but has NO wrapping text beside it -- a "
                f"text-less float just leaves an L-shaped void. Center the "
                f"figure (.figure) with text full-width below instead."
            )
            continue
        deficit = float(bv["fig_bottom"]) - float(tb)
        line_h = float(bv.get("line_h", 0) or 0)
        ratio = deficit / fig_h
        if ratio > beside_void and deficit > 1.5 * max(line_h, 1.0):
            warns.append(
                f"FIG/BESIDE-TEXT-VOID: '{ascii_safe(bv.get('src', ''))}' -- "
                f"the wrapping text stops {ratio * 100:.0f}% of the figure's "
                f"height short of its bottom, leaving an L-shaped void beside "
                f"the figure's lower half. Best fix: lengthen the text with "
                f"paper-sourced detail until it fills the figure height, or "
                f"shrink the figure to the text height. Centering (.figure, "
                f"text full-width below) only helps a WIDE figure (aspect > "
                f"~1.3) -- centering a square or tall figure at a width that "
                f"fits the column just trades the L-void for symmetric side "
                f"voids and shrinks the figure."
            )

    # ---- Gate B: typography orphans ----
    for n in data.get("orphans", []):
        txt: str = n["text"]
        if not txt:
            continue
        last = txt[-1]
        if last not in ORPHAN_GLYPHS:
            continue
        if not re.search(r"\s", txt[:-1]):
            continue
        ws = (n["ws"] or "").lower()
        if "nowrap" in ws or "pre" in ws:
            continue
        warns.append(
            f"ORPHAN: <{ascii_safe(n['tag'])} class='{ascii_safe(n['cls'])}'> "
            f"text '{ascii_safe(txt[:48])}' ends with '{ascii_safe(last)}' "
            f"and may wrap alone. Apply `white-space: nowrap` or use &nbsp; "
            f"before the trailing glyph."
        )

    # ---- Gate B (prose): a stranded RUNT last line (width-based) ----
    # The wrap-geometry sibling of the stat/num orphan above: a `.callout` /
    # `.body-text` / `.caption` / `.section-title` / `.card p` / `.card li` /
    # `.fb-text` (or a `<br>`-delimited segment of one) whose last visual line
    # fills < ~35% of the typeset measure for ordinary prose -- the `.fb-text`
    # banner uses the higher ~80% BANNER_FILL_FRAC (see the per-item `banner`
    # branch below). Judged by WIDTH, not word count, so a short TWO-word tail flags
    # while a single LONG word that fills the line does not. SKILL.md Gate B
    # forbids this; the stat/num scan can't see it. Gluing the last two tokens
    # with &nbsp; pulls the prior word down onto the last line and widens it
    # above the threshold, so the recommended fix still clears the gate. The
    # framework banner (`.fb-text`) carries a `banner` flag and a higher bar
    # (BANNER_FILL_FRAC): it must read as a FILLED rectangle, so it gets a
    # fill-the-rectangle message (reflow via width, font size, and/or rewording
    # -- combinable, in moderation) instead of the runt/glue one.
    for w in data.get("widows", []):
        if w.get("banner"):
            warns.append(
                f"BANNER WIDOW: <{ascii_safe(w['tag'])} class='{ascii_safe(w['cls'])}'> "
                f"the framework banner is the poster's most prominent block, but its "
                f"last line fills only {int(w['frac'])}% of the typeset width "
                f"('{ascii_safe(w['word'])}') -- it should read as a filled rectangle "
                f"(SKILL.md Gate B). Reflow it to a near-full last line by any of, or "
                f"a moderate mix of: (a) tune the .fb-text width (its flex ratio vs "
                f".banner-stats -- fill jumps non-monotonically, try a few) without "
                f"starving the stat boxes; (b) bump the .fb-text font size one --fs-* "
                f"step, if it shifts the wrap (also makes the block bolder), without "
                f"overflowing the banner or colliding with the stats; (c) expand the "
                f"wording with a few truthful, on-message words (keep .fb-text under "
                f"~400 chars -- past that the gate only judges a single stranded word, not banner fill); (d) trim it to one-fewer "
                f"full line. Keep the change proportionate -- don't push one lever to an "
                f"extreme (e.g. a blown-up font) just to clear the gate, and never force "
                f"it with text-align: justify / text-align-last or letter-spacing "
                f"padding. Re-render and look after. "
                f"Context: '{ascii_safe(w['text'])}'."
            )
        else:
            mode = w.get("mode", "std")
            if mode == "long":
                where = (" (long running prose -- judged by the single-"
                         "stranded-word bar only)")
            elif mode == "generic":
                where = (" (unlisted block type, judged by the single-"
                         "stranded-word bar; a lone stranded word reads "
                         "wrong in ANY block)")
            else:
                where = ""
            warns.append(
                f"WIDOW: <{ascii_safe(w['tag'])} class='{ascii_safe(w['cls'])}'> "
                f"wraps to a stranded last line that fills only "
                f"{int(w['frac'])}% of the typeset width ('{ascii_safe(w['word'])}'), "
                f"a runt (SKILL.md Gate B){where}. Fix by REWORDING first: "
                f"expand or trim a few words so the break lands on a phrase "
                f"boundary and the last line carries more of the measure (if "
                f"alignment is already tuned, swap a word for a longer synonym "
                f"to keep the line count). On a CENTERED heading/title use "
                f"text-wrap: balance instead. &nbsp;-glue is a LAST RESORT for "
                f"a leading marker or a tight stat cell only -- glue at most "
                f"two tokens; never chain more (a fused multi-word unit wraps "
                f"early and tears a hole in the line above -- the GLUE-CHAIN "
                f"gate flags it). Context: '{ascii_safe(w['text'])}'."
            )

    # ---- Gate B (glue chains): >=3 words fused with &nbsp; ----
    # The lazy widow "fix": fusing the last N words so the last line clears
    # the runt bar. The fused unit is unbreakable, so it wraps EARLY as a
    # whole -- the line above breaks with room to spare and the paragraph
    # ships a mid-line hole the WIDOW width test cannot see (it only measures
    # the LAST line). Numeric runs (stat comparisons) are exempted JS-side.
    for gc in data.get("glueChains", []):
        warns.append(
            f"GLUE-CHAIN: <{ascii_safe(gc['tag'])} class='{ascii_safe(gc['cls'])}'> "
            f"fuses {gc['words']} words with &nbsp; "
            f"('{ascii_safe(gc['chain'])}') -- an unbreakable unit this long "
            f"wraps early as a whole and tears a hole in the line above. "
            f"Unglue it and REWORD the sentence instead (SKILL.md Gate B); "
            f"keep &nbsp; for at most two tokens (a leading marker, a stat "
            f"cell)."
        )

    # ---- Gate B (text-wrap census): wrap protection dropped wholesale ----
    census = data.get("wrapCensus", [])
    unprot = [c for c in census if not c.get("protected")]
    min_unprot = getattr(
        args, "min_unprotected_wraps", DEFAULT_MIN_UNPROTECTED_WRAPS)
    if census and len(unprot) >= min_unprot:
        sample_cls = []
        for c in unprot:
            cls_toks = str(c.get("cls") or "").split()
            name = (
                ("." + cls_toks[0]) if cls_toks
                else f"<{c.get('tag', '?')}>"
            )
            if name not in sample_cls:
                sample_cls.append(name)
            if len(sample_cls) >= 5:
                break
        warns.append(
            f"TEXT-WRAP: {len(unprot)} of {len(census)} wrapped text blocks "
            f"carry neither `text-wrap: pretty` nor `balance` (e.g. "
            f"{ascii_safe(', '.join(sample_cls))}) -- the templates' "
            f"protective defaults were dropped, which is how custom skeletons "
            f"strand single-word widows and ragged titles. Add the base "
            f"defenses block (SKILL.md Step 3): `pretty` on prose, "
            f"`balance` on centered display text."
        )

    # ---- Gate C: space-between fill ----
    for c in data.get("cols", []):
        col_h = float(c["column_h"])
        excess = float(c["max_excess_px"])
        if col_h <= 0:
            continue
        fill = excess / col_h
        if fill > args.max_space_between_fill:
            warns.append(
                f"SPACE-BETWEEN: column {c['column_index']} has a "
                f"{excess:.0f} px inter-card gap "
                f"({fill * 100:.1f}% of column height, stated gap "
                f"{c['stated_gap_px']:.0f} px). Balance via "
                f"meaningful content, not justify-content. See "
                f"Gate C in SKILL.md."
            )

    # ---- Gate C (one card): trailing whitespace below the last line ----
    for c in data.get("cards", []):
        ch = float(c["card_h"])
        tr = float(c["trailing_px"])
        if ch <= 0 or tr <= 0:
            continue
        ratio = tr / ch
        if ratio > args.max_card_trailing:
            warns.append(
                f"CARD/TRAILING: card {c['card_index']} fills only "
                f"{100 - ratio * 100:.0f}% of its height -- {tr:.0f} px "
                f"({ratio * 100:.0f}%) blank below the last line. A card "
                f"stretched to align (flex:1) but padded with whitespace "
                f"clears the bottom-edge gate yet reads as unfinished. Fill "
                f"with real content, grow a figure, or shrink the canvas. "
                f"See Gate C in SKILL.md."
            )

    # ---- Gate C (one card): mid-card void between two stacked children ----
    iv_ratio = getattr(args, "max_card_inner_void", DEFAULT_CARD_INNER_VOID)
    iv_floor = getattr(
        args, "min_card_inner_void_px", DEFAULT_CARD_INNER_VOID_PX)
    for c in data.get("innerVoids", []):
        ch = float(c["card_h"])
        excess = float(c["excess"])
        if ch <= 0 or excess <= iv_floor:
            continue
        if excess / ch <= iv_ratio:
            continue
        between = ""
        if c.get("above") and c.get("below"):
            between = (f" between <{ascii_safe(c['above'])}> and "
                       f"<{ascii_safe(c['below'])}>")
        warns.append(
            f"CARD/INNER-VOID: a <{ascii_safe(c['cls'])}> card has a "
            f"{excess:.0f} px gap ({excess / ch * 100:.0f}% of card height, "
            f"stated row-gap {c['stated_gap']:.0f} px){between} -- a void in "
            f"the MIDDLE of the card, below the last real block and above a "
            f"bottom-pinned one. The usual cause is an equal-height row "
            f"(grid/flex `align-items: stretch`) of cards with unequal "
            f"content where the short card pins its tail with "
            f"`margin-top: auto` (or `justify-content: space-*`). Fill the "
            f"short card with substance, or drop the bottom-pin / "
            f"equal-height stretch so it hugs its content. See Gate C in "
            f"SKILL.md."
        )

    # ---- Gate C (tracks): the same void inside a header/footer track ----
    # A vertical masthead spine / side rail is neither a measure column nor a
    # `.card`, so SPACE-BETWEEN, CARD/TRAILING and CARD/INNER-VOID are all
    # blind there. Same thresholds as the card check. The fix ORDER matters
    # (SKILL.md "Slack in a track"): real content first; then a CONSISTENT
    # one-step type bump applied to a whole role -- never a single block
    # blown up to eat one gap, which ships a patchwork of sizes; then narrow
    # the track. Never absorb slack with justify-content: space-*.
    for t in data.get("trackVoids", []):
        th = float(t.get("track_h", 0) or 0)
        excess = float(t.get("excess", 0) or 0)
        if th <= 0 or excess <= iv_floor:
            continue
        if excess / th <= iv_ratio:
            continue
        between = ""
        if t.get("above") and t.get("below"):
            between = (f" between <{ascii_safe(t['above'])}> and "
                       f"<{ascii_safe(t['below'])}>")
        sb = (" (`justify-content: space-between` is stretching it -- that "
              "is the whitespace-stretch SKILL.md forbids on any track)"
              if t.get("space_between") else "")
        warns.append(
            f"TRACK/INNER-VOID: the {ascii_safe(t.get('role', 'track'))} "
            f"track <{ascii_safe(t.get('cls', ''))}> has a {excess:.0f} px "
            f"gap ({excess / th * 100:.0f}% of track height, stated row-gap "
            f"{t['stated_gap']:.0f} px){between}{sb}. Absorb the slack with "
            f"substance, in this order: (1) real content the track earns "
            f"(a legend row, a mini-figure, a fuller byline); (2) bump the "
            f"track's SUBORDINATE text one --fs-* step -- applied to the "
            f"whole role consistently (every legend row, the whole byline), "
            f"never one block alone, and keep it below the track's display "
            f"register; (3) narrow the track and give the width back to the "
            f"body. Never stretch with justify-content: space-*. See Slack "
            f"in a track, SKILL.md."
        )

    # ---- Gate G: composed text/ground contrast ----
    # Declared token pairs are style_check's job; this judges what actually
    # rendered. Dedup by (class, fg, bg) so one styling mistake repeated in
    # ten spans reads as one warning, not ten.
    min_contrast = getattr(args, "min_contrast", DEFAULT_MIN_CONTRAST)
    seen_contrast: dict[tuple, dict] = {}
    for c in data.get("contrasts", []):
        ratio = float(c.get("ratio", 99))
        if ratio >= min_contrast:
            continue
        key = (str(c.get("cls", "")), str(c.get("fg", "")),
               str(c.get("bg", "")))
        prev = seen_contrast.get(key)
        if prev is None:
            entry = dict(c)
            entry["count"] = int(c.get("count", 1) or 1)
            seen_contrast[key] = entry
        else:
            prev["count"] += int(c.get("count", 1) or 1)
            if ratio < float(prev.get("ratio", 99)):
                prev["ratio"] = ratio
                prev["text"] = c.get("text", prev.get("text"))
    for entry in sorted(seen_contrast.values(),
                        key=lambda e: float(e.get("ratio", 99)))[:10]:
        more = (f" (+{entry['count'] - 1} more run(s) of this class/color "
                f"pair)" if entry["count"] > 1 else "")
        warns.append(
            f"CONTRAST: <{ascii_safe(entry['tag'])} "
            f"class='{ascii_safe(entry['cls'])}'> "
            f"'{ascii_safe(entry['text'])}' renders {entry['fg']} on "
            f"{entry['bg']} = {entry['ratio']}:1 (floor "
            f"{min_contrast}:1){more}. The usual cause: an inline "
            f"emphasis/highlight class sets a background but INHERITS its "
            f"text color from a different ground -- any class that paints a "
            f"background must declare its own `color`. Fix the token pairing "
            f"(use the matching *-ink token), then re-render and look."
        )

    # ---- Gate D: <br> inside a flex container ----
    # A <br> that is a direct child of a flex container is blockified into
    # a flex item and creates NO line break, so intended multi-line text
    # collapses onto one row. Detectable only at render time (getComputed-
    # Style), which is why it lives here and not in preflight's static scan.
    for fb in data.get("flexbr", []):
        cls = str(fb.get("cls", ""))
        cls_attr = f' class="{ascii_safe(cls)}"' if cls else ""
        warns.append(
            f"LAYOUT/FLEX-BR: <{ascii_safe(fb['tag'])}{cls_attr}> is "
            f"display:flex (flex-direction:{fb['dir']}) with a direct <br> "
            f"child -- the <br> is blockified into a flex item and creates "
            f"NO line break, so intended multi-line content collapses onto "
            f"one row. Wrap each line in a <span> and use "
            f"flex-direction:column, or make the wrapper a plain block."
        )

    # ---- Gate E: header logos / QR / title squeeze ----
    # Header logos live outside any card/hero, so Gates A-D never see
    # them. Read defensively (getattr) like tall_min above.
    logo_max_w = getattr(
        args, "logo_max_width_ratio", DEFAULT_LOGO_MAX_WIDTH_RATIO)
    logo_qr_tol = getattr(args, "logo_qr_tol", DEFAULT_LOGO_QR_TOL)
    right_max = getattr(
        args, "rightblock_max_ratio", DEFAULT_RIGHTBLOCK_MAX_RATIO)
    title_min = getattr(args, "title_min_ratio", DEFAULT_TITLE_MIN_RATIO)
    title_offset_max = getattr(
        args, "title_offset_max", DEFAULT_TITLE_OFFSET_MAX)
    header_w = float(data.get("header_w", 0) or 0)
    header_h = float(data.get("header_h", 0) or 0)
    header_cx = float(data.get("header_cx", 0) or 0)
    # Vertical-rail masthead (portrait title spine, DESIGN-AXES Axis 1
    # P5): the horizontal-strip calibrations below (LOGO/WIDE %, the QR
    # height match, TITLE-SQUEEZED/-OFFCENTER) mis-fire on a tall narrow
    # rail and are swapped for rail checks; see RAIL_MIN_ASPECT.
    rail_header = header_w > 0 and header_h / header_w > RAIL_MIN_ASPECT
    # content-box edges (used by the overflow checks; left/right also cap
    # the logo width in rail mode).
    content_l = float(data.get("header_content_left", 0) or 0)
    content_r = float(data.get("header_content_right", 0) or 0)
    content_t = float(data.get("header_content_top", 0) or 0)
    content_b = float(data.get("header_content_bottom", 0) or 0)
    qr_h = max((float(q.get("rendered_h", 0)) for q in data.get("qrs", [])),
               default=0.0)
    wide_lo, wide_hi = LOGO_WIDE_QR_BAND
    for lg in data.get("logos", []):
        lw = float(lg.get("rendered_w", 0))
        lh = float(lg.get("rendered_h", 0))
        nw = float(lg.get("natural_w", 0))
        nh = float(lg.get("natural_h", 0))
        src_l = str(lg.get("src", "")).lower()
        # Same SVG exemption as FIG/BROKEN above: zero natural size is
        # legitimate for vector images.
        src_path = src_l.split("?", 1)[0].split("#", 1)[0]
        is_svg = (
            src_path.endswith((".svg", ".svgz"))
            or src_l.startswith("data:image/svg")
        )
        if (nw <= 0 or nh <= 0) and not is_svg:
            warns.append(
                f"LOGO/BROKEN: header logo '{ascii_safe(lg['src'])}' has "
                f"zero natural size -- the image failed to load (missing "
                f"file, 404, or an unreachable remote URL); it will be "
                f"blank in print."
            )
            continue
        if rail_header:
            # In a rail the logo does not compete with the title for
            # horizontal room -- the %-of-header-width cap is meaningless.
            # The real rail defect is a logo wider than the rail itself.
            rail_w = content_r - content_l
            if rail_w > 0 and lw > rail_w + 2.0:
                warns.append(
                    f"LOGO/WIDE: '{ascii_safe(lg['src'])}' renders "
                    f"{lw:.0f}px wide but the vertical-rail masthead's "
                    f"content box is only {rail_w:.0f}px -- it spills past "
                    f"the rail. Shrink the logo (size class on the "
                    f".logo-slot, or width:100% inside the rail); see Logo "
                    f"handling in SKILL.md."
                )
        elif header_w > 0 and lw / header_w > logo_max_w:
            warns.append(
                f"LOGO/WIDE: '{ascii_safe(lg['src'])}' renders at "
                f"{lw / header_w * 100:.0f}% of header width (limit "
                f"{logo_max_w * 100:.0f}%) -- it crowds the title block. "
                f"Set a size class on the .logo-slot (logo-wide caps a "
                f"wordmark); see Logo handling in SKILL.md."
            )
        # The venue badge sits left of the title at its own scale, and a
        # logo-stack is normalized by WIDTH (intentionally NOT QR-height-
        # matched) -- for both, only the broken/width checks above apply;
        # the QR height match is a height-matched-row rule. A rail
        # masthead stacks logos ABOVE the QR, so no height-matched row
        # exists there at all.
        if (rail_header or lg.get("venue") or lg.get("stacked")
                or qr_h <= 0 or lh <= 0):
            continue
        if "logo-wide" in str(lg.get("slot_classes", "")):
            ratio = lh / qr_h
            if not (wide_lo <= ratio <= wide_hi):
                warns.append(
                    f"LOGO/QR-MISMATCH: wide logo '{ascii_safe(lg['src'])}' "
                    f"is {ratio * 100:.0f}% of QR height -- a wide wordmark "
                    f"reads level at {wide_lo * 100:.0f}-"
                    f"{wide_hi * 100:.0f}%. Size it via the logo-wide "
                    f"class or a tokenized variant; see Logo handling "
                    f"in SKILL.md."
                )
        elif abs(lh - qr_h) / qr_h > logo_qr_tol:
            warns.append(
                f"LOGO/QR-MISMATCH: logo '{ascii_safe(lg['src'])}' renders "
                f"{lh:.0f}px tall vs QR {qr_h:.0f}px "
                f"(>{logo_qr_tol * 100:.0f}% off) -- match heights via the "
                f".logo-slot size class so the header strip reads level. "
                f"See Logo handling in SKILL.md."
            )
    if header_w > 0 and not rail_header:
        # Title-squeeze / centring ratios only describe a horizontal
        # strip; a rail's title runs vertically and has no side blocks.
        for hb in data.get("headerBlocks", []):
            w = float(hb.get("w", 0))
            if w <= 0:
                continue
            frac = w / header_w
            if hb.get("kind") == "right" and frac > right_max:
                warns.append(
                    f"HEADER/TITLE-SQUEEZED: header right block "
                    f"('{ascii_safe(hb['cls'])}') takes {frac * 100:.0f}% "
                    f"of header width (limit {right_max * 100:.0f}%) -- "
                    f"that leaves too little room for the centred title. "
                    f"Shrink or stack the logos/QR; see Logo handling in "
                    f"SKILL.md."
                )
            elif hb.get("kind") == "title":
                if frac < title_min:
                    warns.append(
                        f"HEADER/TITLE-SQUEEZED: title block squeezed to "
                        f"{frac * 100:.0f}% of header width (floor "
                        f"{title_min * 100:.0f}%) -- logos/venue/QR are "
                        f"crowding the title. Shrink or stack the side "
                        f"blocks; see Logo handling in SKILL.md."
                    )
                cx = float(hb.get("cx", 0) or 0)
                if header_cx > 0 and cx > 0:
                    off = abs(cx - header_cx) / header_w
                    if off > title_offset_max:
                        warns.append(
                            f"HEADER/TITLE-OFFCENTER: the title sits "
                            f"{off * 100:.0f}% of header width off the "
                            f"poster's centre line (limit "
                            f"{title_offset_max * 100:.0f}%) -- one side "
                            f"block (logo / venue badge / QR) is heavier "
                            f"than the other, pushing the centred title "
                            f"aside. Proper logo/QR sizing and a clean "
                            f"layout come first; if you can rebalance the "
                            f"header (shrink, stack, or move the heavier "
                            f"side, or widen the lighter one) WITHOUT "
                            f"shrinking the logo/QR below a legible size, "
                            f"do so -- otherwise it is an accepted "
                            f"trade-off. See Logo handling in SKILL.md."
                        )

    # Header overflow -- the case the ratio + offset gates miss: both side
    # blocks large but balanced keeps the title centred and each side under
    # its ratio, yet the row overflows the header content box (the centre
    # track is floored at 50%, so it cannot give way). measure's clipping
    # gate does not watch the header, so this is the only signal. We test
    # the BOX edges against the header content box -- not block-vs-title
    # overlap, since a title-block box floored at 50% is intentionally wide
    # (text centred inside whitespace) and would overlap a neighbour's box
    # without the visible text colliding. Runs in BOTH modes: a rail's
    # blocks can spill sideways (too wide for the rail) just as a strip's
    # can, and in rail mode the vertical edges are checked too (the rail
    # stacks its blocks, so the overflow axis is vertical there).
    if header_w > 0 and content_r > content_l:
        for hb in data.get("headerBlocks", []):
            spills_x = (float(hb.get("right", 0)) > content_r + 2.0
                        or float(hb.get("left", 0)) < content_l - 2.0)
            spills_y = (rail_header and content_b > content_t
                        and (float(hb.get("bottom", 0)) > content_b + 2.0
                             or float(hb.get("top", 0)) < content_t - 2.0))
            if not (spills_x or spills_y):
                continue
            if rail_header:
                warns.append(
                    f"HEADER/OVERFLOW: the masthead block "
                    f"'{ascii_safe(hb.get('cls', ''))}' spills past the "
                    f"vertical rail's "
                    f"{'side' if spills_x else 'top/bottom'} edge -- the "
                    f"rail stacks its blocks, so shrink the block or give "
                    f"the stack less content; see Logo handling in "
                    f"SKILL.md."
                )
            else:
                warns.append(
                    f"HEADER/OVERFLOW: the header block "
                    f"'{ascii_safe(hb.get('cls', ''))}' spills past the "
                    f"header edge -- the side blocks (logo / venue badge / "
                    f"QR) are too wide to sit beside the title at its 50% "
                    f"floor, so the row overflows instead of shrinking the "
                    f"title. Shrink or stack the side blocks, or drop one; "
                    f"see Logo handling in SKILL.md."
                )
            break

    # ---- Gate F: framework-banner image slot ----
    # A captioned method figure in the framework banner whose flex-item slot is
    # much wider than the image wastes banner width and steals room from the
    # body. Fires on EITHER a one-sided dead band (image pinned to one side) OR
    # a caption that expands the slot past the image (the half-fix: margin:auto
    # evens the gaps but a long single-line caption still sets the width).
    # Anchored on the img; the shipped `banner-figure` (width:min-content)
    # collapses the slot to the image and never trips it. Gates A/A2 only scan
    # card+hero images, so banner images are otherwise unchecked.
    slot_min_pic_w = getattr(
        args, "banner_slot_min_pic_w", DEFAULT_BANNER_SLOT_MIN_PIC_W)
    slot_min_pic_h = getattr(
        args, "banner_slot_min_pic_h", DEFAULT_BANNER_SLOT_MIN_PIC_H)
    for b in data.get("bannerImgs", []):
        if b.get("slot_is_img"):
            continue  # a bare <img> IS its slot -> no over-allocation possible
        banner_w = float(b.get("banner_w", 0) or 0)
        slot_w = float(b.get("slot_w", 0) or 0)
        rw = float(b.get("rendered_w", 0) or 0)
        rh = float(b.get("rendered_h", 0) or 0)
        nw = float(b.get("natural_w", 0) or 0)
        nh = float(b.get("natural_h", 0) or 0)
        if rw <= 0 or rh <= 0 or banner_w <= 0 or slot_w <= 0:
            continue
        # Visible PICTURE width inside the <img> box (object-fit letterbox),
        # mirroring Gate A: a contain/scale-down/none image leaves internal
        # voids that belong in the side gaps.
        if nw > 0 and nh > 0:
            ar = nw / nh
        elif rh > 0:
            ar = rw / rh
        else:
            continue
        obj_fit = str(b.get("obj_fit", "")).strip().lower()
        if obj_fit in ("contain", "scale-down") and rh > 0 and ar > 0:
            content_w = min(rw, rh * ar)
            if obj_fit == "scale-down" and nw > 0:
                content_w = min(content_w, nw)
        elif obj_fit == "none" and nw > 0:
            content_w = min(rw, nw)
        else:
            content_w = rw
        pic_w = content_w
        if pic_w < slot_min_pic_w or rh < slot_min_pic_h:
            continue  # inline icon / small mark, not a method figure
        void = max(0.0, rw - content_w)
        left_gap = max(0.0, float(b.get("off_left", 0) or 0) + void / 2.0)
        right_gap = max(0.0, float(b.get("off_right", 0) or 0) + void / 2.0)
        slack = left_gap + right_gap
        delta = abs(left_gap - right_gap)
        cap_w = float(b.get("caption_like_w", 0) or 0)

        overallocated = slack >= max(180.0, 0.035 * banner_w, 0.18 * pic_w)
        if not overallocated:
            continue
        # slack >= 180 here, so the delta/slack ratio is always well-defined.
        asymmetric = (
            max(left_gap, right_gap) >= max(140.0, 0.030 * banner_w)
            and delta >= max(120.0, 0.025 * banner_w, 0.12 * pic_w)
            and (delta / slack) >= 0.55
        )
        caption_expanded = (cap_w >= pic_w * 1.15 and cap_w >= slot_w - 6.0)
        if not (asymmetric or caption_expanded):
            continue
        if asymmetric and caption_expanded:
            cause = ("the image is pinned to one side AND a long caption is "
                     "stretching the figure block")
        elif asymmetric:
            cause = "the image is pinned to one side of an over-wide block"
        else:
            cause = ("a long caption is setting the figure-block width -- the "
                     "image is centred but the slot still stretches to the "
                     "caption")
        warns.append(
            f"BANNER/IMAGE-SLOT: '{ascii_safe(b.get('src', ''))}' sits in a "
            f"banner figure slot {slot_w:.0f}px wide while the image is only "
            f"{pic_w:.0f}px -- {slack:.0f}px of unused width beside it "
            f"({cause}). The banner text block beside the figure is its "
            f"explanation, so the figure usually needs NO caption -- drop it. "
            f"Use the captionless `banner-figure` component (width:min-content "
            f"collapses the slot to the image; any short caption wraps at the "
            f"image box and never sets the width; centre a block image with "
            f"margin-inline:auto, not text-align). See banner-figure in "
            f"COMPONENTS.md."
        )

    print(f"[polish] {ascii_safe(html_path.name)}")
    print(f"  figures checked     : {len(data.get('figures', []))}")
    print(f"  stat-like elements  : {len(data.get('orphans', []))}")
    print(f"  prose widows        : {len(data.get('widows', []))}")
    print(f"  glue chains         : {len(data.get('glueChains', []))}")
    print(f"  wrapped text blocks : {len(data.get('wrapCensus', []))}")
    print(f"  space-between cols  : {len(data.get('cols', []))}")
    print(f"  cards checked       : {len(data.get('cards', []))}")
    print(f"  inner-void cards    : {len(data.get('innerVoids', []))}")
    print(f"  tracks w/ void geom : {len(data.get('trackVoids', []))}")
    print(f"  contrast pairs (<7) : {len(data.get('contrasts', []))}")
    print(f"  beside-text floats  : {len(data.get('besideVoids', []))}")
    print(f"  flex/<br> parents   : {len(data.get('flexbr', []))}")
    print(f"  header logos        : {len(data.get('logos', []))}")
    if rail_header:
        print(f"  header masthead     : vertical rail "
              f"({header_w:.0f}x{header_h:.0f}px) -- horizontal "
              f"calibrations (LOGO/WIDE %, LOGO/QR-MISMATCH, TITLE-*) "
              f"swapped for rail checks")
    print(f"  banner images       : {len(data.get('bannerImgs', []))}")
    print(f"  warnings            : {len(warns)}")
    for w in warns:
        print(f"  WARN: {w}")

    if args.strict and warns:
        _eprint("[polish] FAIL -- --strict and warnings present")
        return 1
    print("[polish] PASS" if not warns
          else "[polish] OK (warnings only)")
    return 0
