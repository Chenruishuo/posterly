"""Rule 13: a BEM-modifier class used in the HTML must have a matching CSS
rule in the inline <style>.

Regression for the 3+1 keybox orphan: a generated poster carried
``<div class="keybox keybox--4">`` (4 stat tiles) but its hand-authored
stylesheet defined only the base ``.keybox { repeat(3, 1fr) }`` and dropped
``.keybox.keybox--4 { repeat(4, 1fr) }``. The class was a dead hook, so the
grid fell back to 3 columns and the 4th tile orphaned into a near-empty
second row. This static rule catches the dropped/typo'd variant before render.

One-directional: used implies defined. A predefined-but-unused variant (the
templates ship these for opt-in) is fine and never flagged.
"""
from __future__ import annotations

from pathlib import Path

import style_check


def _rule13(html: str) -> style_check.RuleResult:
    results, _parser, _tok = style_check.run_source_gate(html, Path("p.html"))
    return next(r for r in results if r.id == 13)


_BASE_CSS = ".keybox { display: grid; grid-template-columns: repeat(3, 1fr); }"
_VARIANT_CSS = ".keybox.keybox--4 { grid-template-columns: repeat(4, 1fr); }"


def _doc(css: str, body: str) -> str:
    return f"<html><head><style>{css}</style></head><body>{body}</body></html>"


def test_dangling_modifier_class_fails() -> None:
    html = _doc(_BASE_CSS,
                '<div class="keybox keybox--4"><div class="kb-item">x</div></div>')
    r = _rule13(html)
    assert r.status == "FAIL"
    assert "keybox--4" in r.detail


def test_defined_modifier_class_passes() -> None:
    html = _doc(_BASE_CSS + _VARIANT_CSS,
                '<div class="keybox keybox--4"><div class="kb-item">x</div></div>')
    assert _rule13(html).status == "PASS"


def test_defined_but_unused_variant_is_not_flagged() -> None:
    # The templates predefine keybox--4 for opt-in; HTML doesn't use it here.
    html = _doc(_BASE_CSS + _VARIANT_CSS,
                '<div class="keybox"><div class="kb-item">x</div></div>')
    assert _rule13(html).status == "PASS"


def test_no_modifier_classes_passes() -> None:
    html = _doc(_BASE_CSS, '<div class="keybox"><div class="kb-item">x</div></div>')
    assert _rule13(html).status == "PASS"


def test_compound_selector_counts_as_defined() -> None:
    # The sole definition is the compound `.keybox.keybox--4` -- there is no
    # bare `.keybox--4` selector, yet the variant is genuinely defined.
    html = _doc(_BASE_CSS + _VARIANT_CSS, '<div class="keybox keybox--4"></div>')
    assert _rule13(html).status == "PASS"


def test_modifier_token_boundary_no_substring_match() -> None:
    # Using keybox--40 while only keybox--4 is defined must still FAIL --
    # exact-token comparison, not substring.
    html = _doc(_BASE_CSS + _VARIANT_CSS, '<div class="keybox keybox--40"></div>')
    assert _rule13(html).status == "FAIL"


def test_logo_subtree_modifier_classes_are_exempt() -> None:
    # A user-supplied logo SVG export may carry arbitrary `foo--bar` classes
    # with no matching rule; the logo subtree is exempt (as for the color rules).
    html = _doc(_BASE_CSS,
                '<div data-color-exempt="logo">'
                '<span class="brand--mark">x</span></div>')
    assert _rule13(html).status == "PASS"
