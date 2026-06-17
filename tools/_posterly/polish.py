"""Soft visual-polish gate — runs at Step 6.

Three gates the hard alignment gate cannot see:

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
    ``.body-text`` / ``.caption`` / ``.section-title`` (or a ``<br>``
    segment of one) that wraps so its last visual line is a stranded
    runt -- filling less than 35% of the widest line. Judged by the last
    line's WIDTH as a fraction of the measure (not word count), so a short
    two-word tail flags and a single long word filling the line does not;
    an ``&nbsp;``-glued tail widens the last line above the threshold. A
    trailing figure/icon/table keeps the last line unjudgeable, but a short
    text tail ending in inline math (``by $\\lambda$.``) is caught.
  - **Gate C: space-between fill.** ``justify-content: space-between``
    on a column with one short card produces a giant whitespace gap
    that reads as "this column ran out of things to say". Detected
    when the largest inter-card gap exceeds the column's stated
    ``row-gap`` by > 5% of column height.

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
        if (!REPLACED.test(el.tagName.toUpperCase()) && el.children.length) {
          return;  // a non-replaced container: skip (only leaves + media)
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
  // poster-centre x of the header box, for the title-centring gate below
  const headerCx = headerRect ? headerRect.left + headerRect.width / 2 : 0;
  // content-box edges (inside border + padding), for the overflow gate
  let headerContentLeft = 0, headerContentRight = 0;
  if (header && headerRect) {
    const cs = getComputedStyle(header);
    headerContentLeft = headerRect.left
      + (parseFloat(cs.borderLeftWidth) || 0) + (parseFloat(cs.paddingLeft) || 0);
    headerContentRight = headerRect.right
      - (parseFloat(cs.borderRightWidth) || 0) - (parseFloat(cs.paddingRight) || 0);
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
  //         `.callout`/`.body-text`/`.caption`/`.section-title` that wraps to
  //         a short last line -- the artefact SKILL.md Gate B forbids. We
  //         judge by the last line's WIDTH as a fraction of the widest line
  //         (NOT word count): a short two-word tail is as ugly as a one-word
  //         one, while a single long word that fills the line is not stranded.
  //         Robust to inline <strong>/<code> splitting a word's rects, to
  //         `text-align: justify`, and to sub-pixel / mixed-font-size line tops.
  const widows = [];
  const RUNT_FRAC = 0.35;   // last line < 35% of the measure = stranded runt
  const WIDOW_SEL = '.callout, .body-text, .caption, .section-title,'
                  + ' .card p, .card li';
  document.querySelectorAll(WIDOW_SEL).forEach(el => {
    // Scan only the most specific prose leaf: if this element CONTAINS another
    // candidate (a .callout wrapping a <p class="body-text">), skip it -- the
    // descendant is scanned on its own, so we never double-report one widow.
    if (el.querySelector(WIDOW_SEL)) return;
    // A vrail rail title is a DELIBERATELY narrow stacked column
    // (each word on its own horizontal line, an over-long word broken with a soft
    // hyphen at a syllable boundary the AGENT judges). Its short last line is
    // intentional, not a runt -- where to break is an authoring judgment the agent
    // makes, not a geometry a gate can score -- so it is marked data-vrail-title to
    // opt out of the widow check. See SKILL.md Gate B.
    if (el.hasAttribute('data-vrail-title')) return;
    const cs = getComputedStyle(el);
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
    // Display text (.caption / .callout) gets a higher length cap than running
    // prose: a short stranded last line under a figure is prominent even in a
    // long caption, and the 220-char cap was exactly why the incident caption
    // (231 chars) was never measured.
    const cap = el.matches('.caption, .callout') ? 400 : 220;

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
      if (norm.length === 0 || norm.length > cap) return;     // skip empty / long running prose
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
      if (measure > 0 && (lastW / measure) < RUNT_FRAC) {
        const ord = Array.from(last.tis).sort((a, b) => a - b);
        widows.push({
          tag: el.tagName.toLowerCase(),
          cls: el.className || '',
          frac: Math.floor(lastW / measure * 100),   // floor: a flagged (<35%) line never displays "35%"
          word: ord.map(ti => toks[ti].t).join(' ').slice(0, 40),
          lines: lines.length,
          text: (norm.length > 60) ? ('...' + norm.slice(-57)) : norm,
        });
      }
    });
  });

  // ---- 9) Framework-banner image slot ----
  // A captioned method figure in the optional framework banner whose flex
  // ITEM ("slot") is much wider than the image wastes banner width and steals
  // room from the body. Anchored on the IMG (not <figure>), so any wrapper
  // element the agent picks is covered. The "slot" is the banner's DIRECT
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

  return {figures, orphans, cols, cards, flexbr, besideVoids, widows,
          logos, qrs, header_w: headerW, header_cx: headerCx,
          header_content_left: headerContentLeft,
          header_content_right: headerContentRight, headerBlocks,
          bannerImgs};
}
"""


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

        data = page.evaluate(_POLISH_JS)
        browser.close()

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
        # Hero branch: stop blanket-exempting hero images. The %-of-card AR
        # gates don't fit a hero panel, but a narrow-aspect picture dropped
        # into a wide-but-SHORT `.hero-stage` is height-constrained and
        # leaves big symmetric side voids. Flag exactly that shape.
        if role == "hero":
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
                        f"HERO/STAGE-LETTERBOX: '{ascii_safe(f['src'])}' "
                        f"(AR={ar:.2f}) fills only {fill * 100:.0f}% of its "
                        f"hero-stage width -- the stage is {stage_ar:.1f}:1, "
                        f"much wider than the image, so a height-constrained "
                        f"picture leaves big symmetric side voids. Give the "
                        f"figure real vertical room (move a secondary diagram "
                        f"out of the hero into a card), or constrain the "
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
                f"{ratio * 100:.0f}% of card width -- wide figures "
                f"should sit >= {args.wide_min_ratio * 100:.0f}%. "
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
    # `.body-text` / `.caption` / `.section-title` (or a `<br>`-delimited
    # segment of one) whose last visual line fills < ~35% of the typeset
    # measure. Judged by WIDTH, not word count, so a short TWO-word tail flags
    # while a single LONG word that fills the line does not. SKILL.md Gate B
    # forbids this; the stat/num scan can't see it. Gluing the last two tokens
    # with &nbsp; pulls the prior word down onto the last line and widens it
    # above the threshold, so the recommended fix still clears the gate.
    for w in data.get("widows", []):
        warns.append(
            f"WIDOW: <{ascii_safe(w['tag'])} class='{ascii_safe(w['cls'])}'> "
            f"wraps to a stranded last line that fills only "
            f"{int(w['frac'])}% of the typeset width ('{ascii_safe(w['word'])}'), "
            f"a runt (SKILL.md Gate B). Pull a word down -- glue the last two "
            f"tokens with &nbsp;, or reword so the last line carries more of "
            f"the measure. Context: '{ascii_safe(w['text'])}'."
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
    header_cx = float(data.get("header_cx", 0) or 0)
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
        if header_w > 0 and lw / header_w > logo_max_w:
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
        # the QR height match is a height-matched-row rule.
        if lg.get("venue") or lg.get("stacked") or qr_h <= 0 or lh <= 0:
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
    if header_w > 0:
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
        # without the visible text colliding.
        content_l = float(data.get("header_content_left", 0) or 0)
        content_r = float(data.get("header_content_right", 0) or 0)
        if content_r > content_l:
            for hb in data.get("headerBlocks", []):
                if (float(hb.get("right", 0)) > content_r + 2.0
                        or float(hb.get("left", 0)) < content_l - 2.0):
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
    print(f"  space-between cols  : {len(data.get('cols', []))}")
    print(f"  cards checked       : {len(data.get('cards', []))}")
    print(f"  beside-text floats  : {len(data.get('besideVoids', []))}")
    print(f"  flex/<br> parents   : {len(data.get('flexbr', []))}")
    print(f"  header logos        : {len(data.get('logos', []))}")
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
