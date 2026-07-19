"""Identity mark (identity-v1): the posterly ⊕ registration glyph baked into
every poster as a corner-signature (always-on) + woven-signature (authoring).

Three layers of coverage:

  1. Pure preflight contract (``identity_mark_problems``) -- presence / count /
     anonymity reverse-check / referential integrity. No Playwright.
  2. Template structure -- all three shipped templates carry the contract, the
     shared #psReg sprite, and a corner mark; the symbol is byte-identical
     across them; the corner is absolutely positioned (so it can't perturb
     measure's column spread).
  3. Chromium-gated polish behaviour -- the widow blind-spot fix (a woven mark
     at a line end must NOT suppress the runt check) and the corner / woven
     soft advisories.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from _posterly import polish as _polish
from _posterly import preflight

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = [
    REPO_ROOT / "templates" / "landscape_4col_neutral.html",
    REPO_ROOT / "templates" / "landscape_hero_neutral.html",
    REPO_ROOT / "templates" / "portrait_2col_neutral.html",
]

# The canonical ⊕ sprite, VERBATIM from the templates (incl. fill/stroke: a
# bare <line> defaults to stroke:none and would render as a lone disc). The
# gate verifies the canonical structure, so the fixture must be the real
# glyph, not an approximation the tests would then bless.
_SPRITE = (
    '<svg><defs><symbol id="psReg" viewBox="0 0 100 100">'
    '<circle cx="50" cy="50" r="25" fill="none" stroke="currentColor" '
    'stroke-width="8"/>'
    '<line x1="50" y1="7" x2="50" y2="93" stroke="currentColor" '
    'stroke-width="8"/>'
    '<line x1="7" y1="50" x2="93" y2="50" stroke="currentColor" '
    'stroke-width="8"/>'
    '</symbol></defs></svg>')
# A live glyph instance: the <use> must sit inside an <svg> (a bare <use> in
# HTML flow is an unknown element and paints nothing) -- mirrors the templates.
_USE = '<svg><use href="#psReg"/></svg>'


# --------------------------------------------------------------------------
# 1) Pure preflight contract
# --------------------------------------------------------------------------
def _probs(html: str) -> list[str]:
    return preflight.identity_mark_problems(html)


def test_identity_on_with_one_corner_passes() -> None:
    html = f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}' \
           f'<span data-ps-mark="corner">{_USE}</span></div>'
    assert _probs(html) == []


def test_identity_on_missing_corner_fails() -> None:
    assert _probs(f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}</div>')


def test_identity_on_two_corners_fails() -> None:
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<span data-ps-mark="corner">a</span>'
            '<span data-ps-mark="corner">b</span></div>')
    assert _probs(html)


def test_identity_on_two_woven_fails() -> None:
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<span data-ps-mark="corner">a</span>'
            '<span data-ps-mark="woven">x</span>'
            '<span data-ps-mark="woven">y</span></div>')
    assert any("woven" in p for p in _probs(html))


def test_identity_on_missing_woven_is_not_a_preflight_fail() -> None:
    """The woven mark is an authoring rule -> its absence is a soft polish
    advisory, never a preflight hard fail (only the corner is mandatory)."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert _probs(html) == []


def test_identity_off_with_a_mark_fails_reverse_check() -> None:
    """Anonymity must REMOVE marks, not just relax a gate."""
    html = (f'<div data-measure-role="poster" data-ps-identity="off">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert _probs(html)


def test_identity_off_clean_passes() -> None:
    assert _probs('<div data-measure-role="poster" data-ps-identity="off">no marks here</div>') == []


def test_legacy_no_attribute_is_a_noop() -> None:
    """A poster predating the contract carries no data-ps-identity and gets
    no identity enforcement at all."""
    assert _probs('<div class="poster">plain old poster</div>') == []


def test_use_without_symbol_definition_fails() -> None:
    html = f'<div data-measure-role="poster" data-ps-identity="on"><span data-ps-mark="corner">{_USE}</span></div>'
    assert any("psReg" in p for p in _probs(html))


def test_unknown_identity_state_fails() -> None:
    assert _probs(f'<div data-measure-role="poster" data-ps-identity="maybe">{_SPRITE}</div>')


def test_commented_mark_is_not_counted() -> None:
    """The scanner is a DOM walk, so a commented-out example mark is never a
    real element -- an identity=off poster with only a commented mark passes."""
    html = ('<div data-measure-role="poster" data-ps-identity="off">'
            '<!-- <span data-ps-mark="corner">x</span> --></div>')
    assert _probs(html) == []


def test_empty_corner_span_fails_structural_check() -> None:
    """An empty data-ps-mark span passes bare counting but renders nothing --
    preflight now requires each mark to contain its <use href="#psReg">."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"></span></div>')
    assert any("glyph" in p or "renders nothing" in p for p in _probs(html))


def test_symbol_id_on_non_symbol_fails() -> None:
    """id="psReg" must sit on a real <symbol>; on a plain <div> it cannot be
    <use>d, so the reference is unresolved."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on"><div id="psReg"></div>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("psReg" in p for p in _probs(html))


def test_declared_contract_without_state_fails() -> None:
    """A poster that declares the identity-v1 contract but omits the state is a
    NEW poster missing its identity, not a legacy file -- fail it."""
    html = '<div class="poster" data-posterly-contract="identity-v1">x</div>'
    assert _probs(html)


def test_generator_meta_without_state_fails() -> None:
    """The posterly generator <meta> is also a 'this is a posterly poster'
    signal -- with no data-ps-identity it must fail, not no-op as legacy."""
    html = ('<head><meta name="generator" content="posterly"></head>'
            '<body><div class="poster">x</div></body>')
    assert _probs(html)


def test_empty_symbol_fails() -> None:
    """<symbol id="psReg"></symbol> resolves but draws nothing -- gate-green
    but blank PDF. Must fail on the empty symbol."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg"></symbol></defs></svg>'
            '<span data-ps-mark="corner"><svg><use href="#psReg"/></svg>'
            '</span></div>')
    assert any("empty" in p for p in _probs(html))


def test_anchor_href_is_not_counted_as_use() -> None:
    """Only a <use> tag counts as a glyph reference -- a stray <a href="#psReg">
    must not rescue an empty corner span."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"></span>'
            f'<a href="#psReg">x</a></div>')
    assert _probs(html)


def test_wrong_case_fragment_fails() -> None:
    """Fragment ids are case-sensitive: <use href="#psreg"> does not resolve to
    the #psReg symbol, so the corner has no glyph."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"><svg><use href="#psreg"/></svg>'
            f'</span></div>')
    assert _probs(html)


def test_live_ornament_when_identity_on_fails() -> None:
    """identity-v1 supersedes .ornament -- a live one under "on" duplicates the
    corner mark and is rejected."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<div class="ornament">LAB</div></div>')
    assert any("ornament" in p for p in _probs(html))


def test_live_ornament_when_anonymous_fails() -> None:
    """Under "off", a live .ornament lab watermark would leak identity -- reject
    it (anonymity must strip identifying marks, not just the ⊕)."""
    html = '<div data-measure-role="poster" data-ps-identity="off"><div class="ornament">LAB</div></div>'
    assert any("ornament" in p for p in _probs(html))


def test_generator_meta_reversed_attr_order_recognized() -> None:
    """The generator-meta trigger is attribute-order-agnostic."""
    html = ('<head><meta content="posterly" name="generator"></head>'
            '<body><div class="poster">x</div></body>')
    assert _probs(html)


def test_data_name_meta_does_not_false_trigger() -> None:
    """data-name / data-content must NOT be read as the generator meta."""
    html = ('<head><meta data-name="generator" data-content="posterly"></head>'
            '<body><div class="poster">x</div></body>')
    assert _probs(html) == []


def test_empty_g_symbol_referenced_fails() -> None:
    """A symbol whose only child is an empty <g> draws nothing -- a container
    tag is not a drawable shape."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg"><g></g></symbol></defs></svg>'
            '<span data-ps-mark="corner"><svg><use href="#psReg"/></svg>'
            '</span></div>')
    assert any("empty" in p for p in _probs(html))


def test_unreferenced_empty_symbol_passes_when_off() -> None:
    """Anonymizing by deleting the marks but leaving a zero-size sprite shell is
    fine -- an UNREFERENCED empty symbol leaks nothing (regression guard)."""
    html = ('<div data-measure-role="poster" data-ps-identity="off">'
            '<svg><defs><symbol id="psReg"></symbol></defs></svg></div>')
    assert _probs(html) == []


def test_unreferenced_empty_symbol_is_noop_for_legacy() -> None:
    """A legacy doc with a stray empty symbol and no identity signals stays a
    no-op (the symbol check must not fire without a reference)."""
    html = ('<svg><defs><symbol id="psReg"></symbol></defs></svg>'
            '<div class="poster">legacy poster</div>')
    assert _probs(html) == []


def test_ornament_card_class_is_not_false_flagged() -> None:
    """`.ornament-card` is a different class token from `.ornament` -- it must
    not trip the supersession check."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<div class="ornament-card">not a watermark</div></div>')
    assert _probs(html) == []


def test_data_class_ornament_is_not_false_flagged() -> None:
    """`data-class="ornament"` is not a `class` attribute."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<div data-class="ornament">x</div></div>')
    assert _probs(html) == []


def test_attribute_strings_shown_as_text_are_not_read() -> None:
    """A poster that DISPLAYS these attribute strings as literal text (e.g. a
    poster about posterly) must not have that text read as real state/marks."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<pre>set data-ps-identity="off" and add data-ps-mark="corner"'
            f'</pre></div>')
    assert _probs(html) == []


def test_rehost_leaves_stale_empty_mark_fails() -> None:
    """Per-mark containment: re-hosting the woven mark but leaving an empty
    second mark behind (a plausible edit slip) fails even though the global
    mark/use counts balance."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<span data-ps-mark="woven"></span></div>')
    assert any("wrap no" in p for p in _probs(html))


def test_mark_outside_poster_root_still_counts() -> None:
    """The WHOLE file prints: an absolutely-positioned second corner left
    outside the poster div still lands on the PDF, so marks are counted
    document-wide -- two corners fail."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span></div>'
            f'<span data-ps-mark="corner">{_USE}</span>')
    assert any("exactly one" in p for p in _probs(html))


def test_template_subtree_is_skipped() -> None:
    """A poster stashed inside an inert <template> is not the live poster."""
    html = ('<template><div data-measure-role="poster" data-ps-identity="on">'
            '<span data-ps-mark="corner"></span></div></template>'
            '<div class="poster">real legacy poster</div>')
    assert _probs(html) == []


# ---- Round-4 hardening: reverse accounting + SVG context + scope ----------
def test_off_with_unwrapped_live_use_fails() -> None:
    """Anonymity leak: the author deleted data-ps-mark but LEFT the
    <svg><use href="#psReg"> element, so a ⊕ still paints. A live use with no
    mark must fail under "off" (the old 'count corner/woven only' passed it)."""
    html = (f'<div data-measure-role="poster" data-ps-identity="off">{_SPRITE}'
            f'<span data-color-exempt="logo">{_USE}</span></div>')
    assert _probs(html)


def test_on_with_extra_orphan_use_fails() -> None:
    """A valid corner PLUS a stray <use> outside any mark paints a third glyph.
    Every live use must belong to a mark."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>{_USE}</div>')
    assert any("outside" in p for p in _probs(html))


def test_misspelled_mark_type_fails() -> None:
    """A typo'd data-ps-mark ("wovne") is not enforced and, under "off", could
    still carry a glyph -- only corner/woven are valid mark values."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<span data-ps-mark="wovne">{_USE}</span></div>')
    assert any("other than" in p for p in _probs(html))


def test_two_uses_in_one_mark_fails() -> None:
    """Each mark is exactly one registration glyph."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"><svg><use href="#psReg"/>'
            f'<use href="#psReg"/></svg></span></div>')
    assert any("more than one" in p for p in _probs(html))


def test_bare_use_in_mark_without_svg_fails() -> None:
    """A <use> in HTML flow (not inside an <svg>) is an unknown element that
    paints nothing -- the mark is effectively empty."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"><use href="#psReg"/></span></div>')
    assert any("wrap no" in p for p in _probs(html))


def test_void_element_mark_fails() -> None:
    """A void element (<img>) can't wrap a <use>, so a corner placed on one is
    an empty mark -- it must be flagged (it silently passed before)."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<img data-ps-mark="corner"></div>')
    assert _probs(html)


def test_mark_on_poster_root_element_fails() -> None:
    """A data-ps-mark on the poster root itself is hard-rejected: ANY
    descendant <use> would satisfy its containment, which is not the
    documented corner/woven placement -- even with a valid use inside."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on"'
            f' data-ps-mark="corner">{_SPRITE}{_USE}</div>')
    assert any("poster root" in p for p in _probs(html))


def test_earlier_stray_state_element_does_not_hijack_root() -> None:
    """Scope is anchored to data-measure-role="poster": a stray earlier element
    carrying data-ps-identity="off" must NOT become the root and shadow the real
    poster (which would let the real, marked poster pass as 'anonymous')."""
    html = ('<div hidden data-ps-identity="off"></div>'
            f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert _probs(html) == []


def test_symbol_outside_svg_fails() -> None:
    """A <symbol id="psReg"> in HTML flow (not inside an <svg>) does not define
    an SVG symbol, so a <use> of it resolves to nothing."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<symbol id="psReg"><circle cx="50" cy="50" r="25"/></symbol>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("not inside an <svg>" in p for p in _probs(html))


def test_circle_with_wrong_radius_attr_is_empty() -> None:
    """<circle rx="25"> (rx is an ellipse attr) has no drawable radius -> the
    symbol is empty."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg"><circle cx="50" cy="50" rx="25"/>'
            '</symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("empty" in p for p in _probs(html))


def test_symbol_of_only_nested_use_is_empty() -> None:
    """A #psReg symbol whose only content is a nested <use> is rejected as
    empty: the indirection can dangle or self-recurse, which a static scan
    cannot resolve -- the canonical ⊕ is plain shapes with explicit geometry."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs>'
            '<path id="glyphParts" d="M0 0 L10 10"/>'
            '<symbol id="psReg"><use href="#glyphParts"/></symbol>'
            '</defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("empty" in p for p in _probs(html))


def test_first_of_duplicate_psreg_symbol_wins() -> None:
    """The browser resolves the FIRST #psReg definition; if it is empty, a later
    non-empty duplicate must not rescue it."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs>'
            '<symbol id="psReg"></symbol>'
            '<symbol id="psReg"><circle cx="50" cy="50" r="25"/></symbol>'
            '</defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("empty" in p for p in _probs(html))


# ---- Round-5 hardening: misplaced state, defs leaks, namespace, geometry ---
def test_misplaced_state_off_outside_root_fails() -> None:
    """An author writes data-ps-identity="off" on the WRONG element: the old
    behaviour silently treated the poster as legacy (mark still prints while
    the author believes it's anonymous). It must fail loudly instead."""
    html = (f'<div data-measure-role="poster">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span></div>'
            f'<div data-ps-identity="off"></div>')
    assert any("NOT the poster root" in p for p in _probs(html))


def test_state_on_root_ignores_stray_state_elsewhere() -> None:
    """A correct root state wins: an extra stray state attr elsewhere neither
    hijacks (round-4 fix) nor triggers the misplaced-state failure."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span></div>'
            f'<div data-ps-identity="off"></div>')
    assert _probs(html) == []


def test_pattern_reference_leaks_under_off_fails() -> None:
    """Anonymity leak via indirection: a #psReg <use> inside a <pattern> is not
    a direct instance, but the pattern can reach the canvas via
    fill="url(#...)". Under "off", EVERY #psReg reference must be gone."""
    html = ('<div data-measure-role="poster" data-ps-identity="off">'
            '<svg><defs>'
            '<symbol id="psReg"><circle cx="50" cy="50" r="25"/></symbol>'
            '<pattern id="p" width="10" height="10">'
            '<use href="#psReg"/></pattern>'
            '</defs>'
            '<rect width="100" height="100" fill="url(#p)"/></svg></div>')
    assert any("#psReg reference" in p for p in _probs(html))


def test_use_inside_foreignobject_is_not_live() -> None:
    """<foreignObject> switches back to the HTML namespace: a <use> inside it
    is an unknown HTML element that paints nothing, so a mark relying on it is
    empty."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"><svg><foreignObject>'
            f'<use href="#psReg"></use>'
            f'</foreignObject></svg></span></div>')
    assert any("wrap no" in p for p in _probs(html))


def test_use_inside_filter_is_not_live() -> None:
    """<filter> is a non-rendering definition context -- a mark whose only
    <use> sits inside one paints nothing."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"><svg><filter id="f">'
            f'<use href="#psReg"/></filter></svg></span></div>')
    assert any("wrap no" in p for p in _probs(html))


def test_empty_href_beats_xlink_href() -> None:
    """Per SVG2 (and Chromium), an EXISTING href attribute wins over
    xlink:href even when empty -- such a <use> resolves to nothing, so the
    mark is empty; the xlink fallback must not rescue it."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"><svg>'
            f'<use href="" xlink:href="#psReg"/></svg></span></div>')
    assert any("wrap no" in p for p in _probs(html))


def test_zero_unit_radius_symbol_is_empty() -> None:
    """<circle r="0mm"> has a unit but zero length -- draws nothing. The
    numeric prefix must be strictly positive whatever the unit."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg">'
            '<circle cx="50" cy="50" r="0mm"/></symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("empty" in p for p in _probs(html))


def test_shapes_only_in_nested_defs_are_not_drawable() -> None:
    """Shapes tucked inside a nested <defs> INSIDE the symbol don't paint when
    the symbol is instanced -- the symbol is effectively empty."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg"><defs>'
            '<circle cx="50" cy="50" r="25"/></defs></symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("empty" in p for p in _probs(html))


def test_g_wrapped_glyph_in_symbol_is_canonical() -> None:
    """A <g>-wrapped canonical glyph stays on the symbol's render path --
    grouping is a legitimate authoring variation, not a deviation."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg"><g>'
            '<circle cx="50" cy="50" r="25"/>'
            '<line x1="50" y1="7" x2="50" y2="93"/>'
            '<line x1="7" y1="50" x2="93" y2="50"/>'
            '</g></symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert _probs(html) == []


# ---- Round-6 hardening: document-wide accounting, first-id, canonical ⊕ ----
def test_off_mark_outside_root_fails() -> None:
    """Anonymity leak: a corner-sig wrapper accidentally left AFTER the poster
    div (a misplaced </div> away) still prints -- absolute positioning puts it
    on the page regardless of which subtree it sits in. "off" must count
    document-wide."""
    html = (f'<div data-measure-role="poster" data-ps-identity="off">{_SPRITE}'
            f'</div><span data-ps-mark="corner">{_USE}</span>')
    assert _probs(html)


def test_duplicate_id_shadows_symbol_fails() -> None:
    """Fragment resolution takes the FIRST id="psReg" in the document, symbol
    or not -- an earlier duplicate id makes every <use> resolve to the wrong
    element (bbox 0x0 in Chromium)."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">'
            f'<div id="psReg"></div>{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("shadows" in p for p in _probs(html))


def test_on_with_pattern_reference_fails() -> None:
    """Under "on", a #psReg <use> tucked in a <pattern> is not a mark-wrapped
    instance but can still paint extra glyphs via fill="url(#...)" -- every
    reference must BE a live mark-wrapped use."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<svg><defs><pattern id="p" width="10" height="10">'
            f'<use href="#psReg"/></pattern></defs>'
            f'<rect width="100" height="100" fill="url(#p)"/></svg></div>')
    assert any("ONLY via its marks" in p for p in _probs(html))


def test_garbage_unit_radius_is_not_canonical() -> None:
    """<circle r="25banana"> is an invalid length -- Chromium renders it as
    zero. A numeric-prefix-only check would call it drawable."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg">'
            '<circle cx="50" cy="50" r="25banana"/>'
            '<line x1="50" y1="7" x2="50" y2="93"/>'
            '<line x1="7" y1="50" x2="93" y2="50"/>'
            '</symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("canonical" in p for p in _probs(html))


def test_single_circle_sprite_is_not_canonical() -> None:
    """The identity glyph is the ⊕ -- one circle + two lines. A bare circle is
    some OTHER mark and must not pass as the posterly identity."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg">'
            '<circle cx="50" cy="50" r="25"/></symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("canonical" in p for p in _probs(html))


def test_shapes_inside_metadata_do_not_count() -> None:
    """<metadata> children never render: a glyph 'defined' only there is
    blank in the browser."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg"><metadata>'
            '<circle cx="50" cy="50" r="25"/>'
            '<line x1="50" y1="7" x2="50" y2="93"/>'
            '<line x1="7" y1="50" x2="93" y2="50"/>'
            '</metadata></symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("empty" in p or "canonical" in p for p in _probs(html))


def test_use_inside_desc_is_not_live() -> None:
    """<desc> content is metadata, not rendering -- a mark whose only <use>
    sits inside one paints nothing (Chromium switches <desc> children back to
    HTML)."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner"><svg><desc>'
            f'<use href="#psReg"/></desc></svg></span></div>')
    assert any("wrap no" in p for p in _probs(html))


# ---- Round-7 hardening: in-root placement, integration points, geometry ----
def test_only_corner_outside_root_fails() -> None:
    """Document-wide counting must COMPLEMENT the root contract, not replace
    it: if the single corner sits outside the poster root, the count is fine
    but the placement contract (bottom-right safe zone of the ROOT, where the
    polish probe scans) is broken."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'</div><span data-ps-mark="corner">{_USE}</span>')
    assert any("OUTSIDE the poster root" in p for p in _probs(html))


def test_only_woven_outside_root_fails() -> None:
    """Same for the woven mark: it must ride content INSIDE the poster."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span></div>'
            f'<span data-ps-mark="woven">{_USE}</span>')
    assert any("OUTSIDE the poster root" in p for p in _probs(html))


def test_symbol_inside_desc_is_shadowed_html() -> None:
    """<desc> is an HTML integration point: a <symbol id="psReg"> inside it is
    an HTML element (namespaceURI xhtml in Chromium), so the first-id
    resolution lands on a non-SVG element and the <use> renders 0x0."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">'
            f'<svg><desc><symbol id="psReg">'
            f'<circle cx="50" cy="50" r="25"/>'
            f'<line x1="50" y1="7" x2="50" y2="93"/>'
            f'<line x1="7" y1="50" x2="93" y2="50"/>'
            f'</symbol></desc></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert _probs(html)


def test_zero_length_lines_are_not_canonical() -> None:
    """<line x1="0" y1="0" x2="0" y2="0"> is syntactically valid but draws
    nothing -- a degenerate cross is not the ⊕."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg">'
            '<circle cx="50" cy="50" r="25"/>'
            '<line x1="0" y1="0" x2="0" y2="0"/>'
            '<line x1="0" y1="0" x2="0" y2="0"/>'
            '</symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("canonical" in p for p in _probs(html))


def test_unclosed_circle_swallowing_lines_fails() -> None:
    """An unclosed <circle> makes the browser nest the two lines INSIDE it,
    where they don't paint -- the render path must not keep counting them
    (shapes propagate only through explicit <g> wrappers)."""
    html = ('<div data-measure-role="poster" data-ps-identity="on">'
            '<svg><defs><symbol id="psReg">'
            '<circle cx="50" cy="50" r="25">'
            '<line x1="50" y1="7" x2="50" y2="93"/>'
            '<line x1="7" y1="50" x2="93" y2="50"/>'
            '</circle></symbol></defs></svg>'
            f'<span data-ps-mark="corner">{_USE}</span></div>')
    assert any("canonical" in p for p in _probs(html))


def test_uppercase_mark_value_fails() -> None:
    """Every consumer matches the mark value case-sensitively (the woven
    sizing CSS, the polish probe) -- a "WOVEN" that a lenient gate accepted
    would miss its sizing rule and blow up to column width. Exact strings
    only."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<span data-ps-mark="WOVEN">{_USE}</span></div>')
    assert any("other than" in p for p in _probs(html))


def test_declarative_shadow_dom_is_rejected() -> None:
    """<template shadowrootmode="open"> RENDERS (declarative shadow DOM) --
    it must not ride the inert-template skip; the scan doesn't model shadow
    scoping, so it is hard-rejected."""
    html = ('<div data-measure-role="poster" data-ps-identity="off">'
            '<template shadowrootmode="open">'
            f'{_SPRITE}<span data-ps-mark="corner">{_USE}</span>'
            '</template></div>')
    assert any("shadow" in p for p in _probs(html))


def test_noscript_fallback_mark_is_not_counted() -> None:
    """The Chromium export runs with scripting enabled, so <noscript> content
    never renders -- a fallback mark inside it must not double-count against
    the real corner (parser-only ghost)."""
    html = (f'<div data-measure-role="poster" data-ps-identity="on">{_SPRITE}'
            f'<span data-ps-mark="corner">{_USE}</span>'
            f'<noscript><span data-ps-mark="corner">{_USE}</span></noscript>'
            f'</div>')
    assert _probs(html) == []


# --------------------------------------------------------------------------
# 2) Template structure
# --------------------------------------------------------------------------
@pytest.mark.parametrize("tpl", TEMPLATES, ids=lambda p: p.name)
def test_template_ships_contract_and_marks(tpl: Path) -> None:
    html = tpl.read_text(encoding="utf-8")
    assert 'data-posterly-contract="identity-v1"' in html
    assert 'data-ps-identity="on"' in html
    assert 'id="psReg"' in html
    assert 'data-ps-mark="corner"' in html
    assert 'href="#psReg"' in html
    # It must PASS the pure identity contract (exactly one corner, symbol
    # defined) with no problems.
    assert preflight.identity_mark_problems(html) == []


def test_symbol_is_byte_identical_across_templates() -> None:
    def symbol(html: str) -> str:
        m = re.search(r'<symbol id="psReg".*?</symbol>', html, re.S)
        assert m, "no #psReg symbol found"
        return m.group(0)

    symbols = {symbol(t.read_text(encoding="utf-8")) for t in TEMPLATES}
    assert len(symbols) == 1, "the #psReg sprite drifted across templates"


@pytest.mark.parametrize("tpl", TEMPLATES, ids=lambda p: p.name)
def test_corner_sig_is_absolutely_positioned(tpl: Path) -> None:
    """Absolute positioning in the padding safe zone is what keeps the corner
    out of the grid / column-spread that measure reads."""
    html = tpl.read_text(encoding="utf-8")
    m = re.search(r'\.corner-sig\s*\{(.*?)\}', html, re.S)
    assert m, "no .corner-sig rule"
    assert "position: absolute" in m.group(1)


@pytest.mark.parametrize("tpl", TEMPLATES, ids=lambda p: p.name)
def test_template_ships_woven_sizing_rule(tpl: Path) -> None:
    """The woven snippet is self-sizing: the template must ship a
    [data-ps-mark="woven"] rule that sizes it to the host text (em), so the
    documented bare <svg> does not blow up to the full column width."""
    html = tpl.read_text(encoding="utf-8")
    m = re.search(r'\[data-ps-mark="woven"\]\s*\{([^}]*)\}', html)
    assert m, 'no [data-ps-mark="woven"] sizing rule'
    body = m.group(1)
    assert "width" in body and "em" in body
    assert "%" not in body  # host-relative em, never a percentage of the column


def test_skill_woven_snippet_is_current() -> None:
    """Guard the documented woven snippet against drift: it must stay
    self-sizing (no hand-coded width/height) and carry the honesty attributes,
    so the render test below exercises the SAME shape agents are told to use."""
    skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r'<span data-ps-mark="woven".*?</span>', skill)
    assert m, "woven snippet not found in SKILL.md"
    snip = m.group(0)
    assert 'data-color-exempt="logo"' in snip
    assert 'aria-hidden="true"' in snip
    assert '<use href="#psReg"' in snip
    assert "width=" not in snip and "height=" not in snip  # self-sizing


# --------------------------------------------------------------------------
# 3) Chromium-gated polish behaviour
# --------------------------------------------------------------------------
def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


chromium = pytest.mark.skipif(
    not _chromium_available(), reason="playwright + chromium not available"
)


def _polish_args(html: Path) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200, mathjax_timeout_ms=5000,
        wide_min_ratio=0.65, tall_max_ratio=0.70, tall_min_ratio=0.36,
        square_min_ratio=0.55, max_space_between_fill=0.05,
        max_card_trailing=0.10, strict=False,
    )


# A 38-char word: far wider than the pinned 240px callout, so it strands the
# short final marker onto a line of its own -> a runt to be judged.
_PEN = "supercalifragilisticexpialidociousword."

_WIDOW_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .poster { position: relative; }
  .callout { width: 240px; font-size: 30px; line-height: 1.3; }
</style></head>
<body>
  <div class="poster" data-measure-role="poster">
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">
      <!-- control: a PLAIN trailing <svg> is MEDIA -> last line unjudgeable
           -> NO widow (guards the default behaviour). -->
      <div class="callout" id="ctrl">alpha __PEN__ noflagctrl.<svg width="12" height="12"></svg></div>
      <!-- woven: the identity mark <svg> (with its #psReg use, like the real
           snippet) is NOT prose media, so the stranded "flagwoven." last line
           MUST still be judged as a runt -> WIDOW. This is the blind-spot fix. -->
      <div class="callout" id="wov">alpha __PEN__ flagwoven.<span data-ps-mark="woven"><svg width="12" height="12"><use href="#psReg"/></svg></span></div>
    </div>
  </div>
  </div>
</body></html>
""".replace("__PEN__", _PEN)


@chromium
def test_woven_mark_does_not_suppress_widow(tmp_path, capsys) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_WIDOW_HTML, encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0  # soft gate
    # The woven-mark line is still judged -> its runt flags.
    assert "flagwoven." in out
    # The plain-svg control is media -> still NOT judged.
    assert "noflagctrl." not in out


_ADVISORY_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .poster { position: relative; }
  .hidden-corner { display: none; }
</style></head>
<body>
  <div class="poster" data-measure-role="poster"
       data-posterly-contract="identity-v1" data-ps-identity="on">
  <svg aria-hidden="true" style="position:absolute;width:0;height:0"><defs>
    <symbol id="psReg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="25"/></symbol>
  </defs></svg>
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">
      <p class="body-text">Short body content that does not widow.</p>
    </div>
  </div>
  <!-- corner mark present but display:none -> renders invisible. And there is
       NO woven mark. Both soft advisories must fire. -->
  <span class="hidden-corner" data-ps-mark="corner"><svg viewBox="0 0 100 100"><use href="#psReg"/></svg></span>
  </div>
</body></html>
"""


@chromium
def test_corner_and_woven_advisories_fire(tmp_path, capsys) -> None:
    poster = tmp_path / "poster.html"
    poster.write_text(_ADVISORY_HTML, encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0  # soft advisories never fail the gate
    assert "IDENTITY/CORNER" in out   # hidden corner -> would not print
    assert "IDENTITY/WOVEN" in out    # identity on + no woven mark


# The verbatim woven snippet from SKILL.md / COMPONENTS.md -- no inline size.
_WOVEN_SNIPPET = ('<span data-ps-mark="woven" data-color-exempt="logo" '
                  'aria-hidden="true"><svg viewBox="0 0 100 100">'
                  '<use href="#psReg"/></svg></span>')


def _woven_css(tpl: Path) -> str:
    """Extract the template's own [data-ps-mark="woven"] CSS so the render test
    exercises the SHIPPED contract, not a hand-written copy."""
    html = tpl.read_text(encoding="utf-8")
    return "\n".join(re.findall(r'\[data-ps-mark="woven"\][^{]*\{[^}]*\}', html))


@chromium
def test_woven_snippet_renders_glyph_scale(tmp_path) -> None:
    """The documented bare-<svg> woven snippet, under the template's shipped
    CSS, must render at inline-glyph scale -- NOT expand to the host width (a
    viewBox-only <svg> with no CSS renders hundreds of px wide)."""
    from playwright.sync_api import sync_playwright

    css = _woven_css(TEMPLATES[0])
    assert '[data-ps-mark="woven"]' in css, "template lost its woven sizing rule"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
      body {{ font-size: 30px; }}
      {css}
    </style></head><body>
      <svg style="position:absolute;width:0;height:0"><defs>
        <symbol id="psReg" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="25" fill="none" stroke="currentColor" stroke-width="8"/>
        </symbol></defs></svg>
      <p>best result 4.05{_WOVEN_SNIPPET}</p>
    </body></html>"""
    poster = tmp_path / "woven.html"
    poster.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(poster.as_uri())
        w = page.eval_on_selector(
            '[data-ps-mark="woven"] svg',
            "el => el.getBoundingClientRect().width")
        browser.close()
    # ~0.82em of 30px font ~= 24.6px; a bare unstyled <svg> would blow up to
    # the paragraph width (hundreds of px). Keep it glyph-scale.
    assert 5 < w < 60, f"woven glyph rendered {w}px -- not inline-glyph scale"


_COMMENTED_WOVEN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .poster { position: relative; min-height: 400px; }
  .corner-sig { position: absolute; right: 20px; bottom: 20px;
                width: 24px; height: 24px; opacity: 0.5; }
  .corner-sig svg { display: block; width: 100%; height: 100%; }
</style></head>
<body>
  <div class="poster" data-measure-role="poster"
       data-posterly-contract="identity-v1" data-ps-identity="on">
  <svg aria-hidden="true" style="position:absolute;width:0;height:0"><defs>
    <symbol id="psReg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="25"/></symbol>
  </defs></svg>
  <div data-measure-role="column">
    <div class="card" data-measure-role="card">
      <p class="body-text">Short body content that does not widow.</p>
    </div>
  </div>
  <span class="corner-sig" data-ps-mark="corner"><svg viewBox="0 0 100 100"><use href="#psReg"/></svg></span>
  <!-- a woven mark ONLY inside this comment -- must not count as present:
  <span data-ps-mark="woven"><svg viewBox="0 0 100 100"><use href="#psReg"/></svg></span> -->
  </div>
</body></html>
"""


@chromium
def test_commented_woven_does_not_suppress_advisory(tmp_path, capsys) -> None:
    """A woven mark that exists ONLY inside an HTML comment must not count as
    present -- the shared identity scanner is a DOM walk (M6), so the
    missing-woven advisory still fires. The visible corner fires no advisory."""
    poster = tmp_path / "poster.html"
    poster.write_text(_COMMENTED_WOVEN_HTML, encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/WOVEN" in out       # commented woven doesn't count
    assert "IDENTITY/CORNER" not in out  # the corner renders visibly


_CORNER_INNER_HIDDEN_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .poster { position: relative; min-height: 400px; }
  .corner-sig { position: absolute; right: 20px; bottom: 20px;
                width: 24px; height: 24px; opacity: 0.5; }
  .corner-sig svg { display: none; }   /* inner glyph hidden -> paints nothing */
</style></head>
<body>
  <div class="poster" data-measure-role="poster"
       data-posterly-contract="identity-v1" data-ps-identity="on">
  <svg aria-hidden="true" style="position:absolute;width:0;height:0"><defs>
    <symbol id="psReg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="25"/></symbol>
  </defs></svg>
  <div data-measure-role="column"><div class="card" data-measure-role="card">
    <p class="body-text">Short body.</p></div></div>
  <span class="corner-sig" data-ps-mark="corner"><svg viewBox="0 0 100 100"><use href="#psReg"/></svg></span>
  </div>
</body></html>
"""


@chromium
def test_corner_with_hidden_inner_glyph_warns(tmp_path, capsys) -> None:
    """The span box is fine but its inner <svg> is display:none, so nothing
    paints -- the deeper corner check (glyph / ink / ancestor opacity) must
    still flag it."""
    poster = tmp_path / "poster.html"
    poster.write_text(_CORNER_INNER_HIDDEN_HTML, encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/CORNER" in out


# Everything about the corner is visible -- but the shape INSIDE the #psReg
# symbol is display:none, so the <use> expands to nothing. Only the
# use.getBBox() probe can see through the shadow tree.
_CORNER_SYMBOL_HIDDEN_HTML = _CORNER_INNER_HIDDEN_HTML.replace(
    ".corner-sig svg { display: none; }   /* inner glyph hidden -> paints nothing */",
    ".corner-sig svg { display: block; width: 100%; height: 100%; }",
).replace(
    '<circle cx="50" cy="50" r="25"/>',
    '<circle cx="50" cy="50" r="25" style="display:none"/>',
)


@chromium
def test_corner_with_hidden_symbol_content_warns(tmp_path, capsys) -> None:
    """display:none on the shape INSIDE the symbol: mark box, inner svg, ink
    and opacity all look fine, but the <use> resolves to nothing (bbox 0x0) --
    the getBBox probe must flag it."""
    # Guard the derived fixture against silent .replace() drift.
    assert 'style="display:none"' in _CORNER_SYMBOL_HIDDEN_HTML
    assert ".corner-sig svg { display: block" in _CORNER_SYMBOL_HIDDEN_HTML
    poster = tmp_path / "poster.html"
    poster.write_text(_CORNER_SYMBOL_HIDDEN_HTML, encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/CORNER" in out


_CORNER_PROBE_BASE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page { size: 24in 36in; margin: 0; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Georgia, serif; }
  .poster { position: relative; min-height: 400px; }
  .corner-sig { position: absolute; right: 20px; bottom: 20px; }
</style></head>
<body>
  <div class="poster" data-measure-role="poster"
       data-posterly-contract="identity-v1" data-ps-identity="on">
  <svg aria-hidden="true" style="position:absolute;width:0;height:0"><defs>
    <symbol id="psReg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="25"/></symbol>
  </defs></svg>
  <div data-measure-role="column"><div class="card" data-measure-role="card">
    <p class="body-text">Short body.</p></div></div>
  __CORNER__
  </div>
</body></html>
"""


def _corner_poster(corner_html: str) -> str:
    out = _CORNER_PROBE_BASE.replace("__CORNER__", corner_html)
    assert corner_html in out  # guard against placeholder drift
    return out


@chromium
def test_corner_probe_finds_glyph_behind_chart_svg(tmp_path, capsys) -> None:
    """The probe must inspect the #psReg use's OWN <svg>, not the first <svg>
    in the mark: here a visible chart svg comes first while the actual glyph
    svg is display:none -- the advisory must still fire."""
    poster = tmp_path / "poster.html"
    poster.write_text(_corner_poster(
        '<span class="corner-sig" data-ps-mark="corner">'
        '<svg width="24" height="24"><rect width="24" height="24"/></svg>'
        '<svg width="24" height="24" style="display:none">'
        '<use href="#psReg"/></svg></span>'
    ), encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/CORNER" in out


@chromium
def test_corner_probe_skips_unrelated_dangling_use(tmp_path, capsys) -> None:
    """A dangling unrelated <use> BEFORE the real #psReg use must not be
    probed in its place -- the corner renders fine, so no false warning."""
    poster = tmp_path / "poster.html"
    poster.write_text(_corner_poster(
        '<span class="corner-sig" data-ps-mark="corner">'
        '<svg width="24" height="24" viewBox="0 0 100 100">'
        '<use href="#missing"/><use href="#psReg"/></svg></span>'
    ), encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/CORNER" not in out


@chromium
def test_corner_use_shifted_out_of_viewport_warns(tmp_path, capsys) -> None:
    """<use x="10000">: the bbox is a healthy 50x50 but the instance is
    clipped out of the svg viewport -- zero identity pixels on the PDF. The
    viewport-intersection check must flag it."""
    poster = tmp_path / "poster.html"
    poster.write_text(_corner_poster(
        '<span class="corner-sig" data-ps-mark="corner">'
        '<svg width="24" height="24" viewBox="0 0 100 100">'
        '<use href="#psReg" x="10000"/></svg></span>'
    ), encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/CORNER" in out


@chromium
def test_corner_owner_svg_moved_off_poster_warns(tmp_path, capsys) -> None:
    """The wrapper stays in the safe zone but the inner owner <svg> is
    position:fixed off-page -- the glyph goes with it. The use-vs-poster
    intersection must flag it (wrapper-rect checks can't)."""
    poster = tmp_path / "poster.html"
    poster.write_text(_corner_poster(
        '<span class="corner-sig" data-ps-mark="corner">'
        '<svg width="24" height="24" viewBox="0 0 100 100"'
        ' style="position:fixed;left:10000px;top:0">'
        '<use href="#psReg"/></svg></span>'
    ), encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/CORNER" in out


@chromium
def test_corner_overflow_visible_shift_is_not_false_flagged(tmp_path,
                                                            capsys) -> None:
    """With overflow:visible on the owner svg, a glyph shifted out of the
    nominal viewport still paints (left, into the poster) -- the viewport
    check must not fire; only real clipping counts."""
    poster = tmp_path / "poster.html"
    poster.write_text(_corner_poster(
        '<span class="corner-sig" data-ps-mark="corner">'
        '<svg width="24" height="24" viewBox="0 0 100 100"'
        ' style="overflow:visible">'
        '<use href="#psReg" x="-150"/></svg></span>'
    ), encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/CORNER" not in out


@chromium
def test_corner_body_opacity_zero_warns(tmp_path, capsys) -> None:
    """opacity:0 ABOVE the poster root (body) blanks the whole page including
    the glyph -- the opacity walk must reach the document root, not stop at
    the poster."""
    html = _corner_poster(
        '<span class="corner-sig" data-ps-mark="corner">'
        '<svg width="24" height="24" viewBox="0 0 100 100">'
        '<use href="#psReg"/></svg></span>'
    ).replace("body { font-family: Georgia, serif; }",
              "body { font-family: Georgia, serif; opacity: 0; }")
    assert "opacity: 0" in html  # guard the .replace against drift
    poster = tmp_path / "poster.html"
    poster.write_text(html, encoding="utf-8")

    rc = _polish.cmd_polish(_polish_args(poster))
    out = "".join(capsys.readouterr())

    assert rc == 0
    assert "IDENTITY/CORNER" in out
