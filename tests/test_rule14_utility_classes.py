"""Rule 14: a numeric utility class used in the HTML must have a matching
CSS rule in the inline <style>.

Regression for the wave-2 figure blow-up: three generated posters referenced
width utilities that no stylesheet rule defined (``w-82``; ``w-50``/``w-58``/
``w-64``; ``w-78``/``w-88``). An undefined width utility on an <img> silently
no-ops, so the figure rendered at NATURAL size and ballooned its column --
each build agent burned a debug round rediscovering the same pit.

Also locks the review fix: "defined" means the class appears in a CSS
SELECTOR (via the same rule-iteration as rule 13), never merely as text
inside a declaration value -- ``content: ".w-82"`` must not count.
"""
from __future__ import annotations

from pathlib import Path

import style_check


def _rule14(html: str) -> style_check.RuleResult:
    results, _parser, _tok = style_check.run_source_gate(html, Path("p.html"))
    return next(r for r in results if r.id == 14)


def _doc(css: str, body: str) -> str:
    return f"<html><head><style>{css}</style></head><body>{body}</body></html>"


_BASE_CSS = ".card { padding: 8px; } .w-60 { width: 60%; }"


def test_dangling_width_utility_fails() -> None:
    html = _doc(_BASE_CSS, '<div class="card"><img class="w-82" src="x.png"></div>')
    r = _rule14(html)
    assert r.status == "FAIL"
    assert "w-82" in r.detail


def test_defined_width_utility_passes() -> None:
    html = _doc(_BASE_CSS, '<div class="card"><img class="w-60" src="x.png"></div>')
    assert _rule14(html).status == "PASS"


def test_class_name_inside_content_string_does_not_count() -> None:
    # The review bypass: `.w-82` appearing only inside a declaration VALUE
    # (a content string) is not a selector -- the utility is still dangling.
    css = _BASE_CSS + ' .x::after { content: ".w-82"; }'
    html = _doc(css, '<div class="card"><img class="w-82" src="x.png"></div>')
    r = _rule14(html)
    assert r.status == "FAIL"
    assert "w-82" in r.detail


def test_class_name_inside_attribute_selector_does_not_count() -> None:
    # Review round 2: `.w-82` inside an attribute VALUE is not a selector.
    css = _BASE_CSS + ' .x[data-note=".w-82"] { display: block; }'
    html = _doc(css, '<div class="card"><img class="w-82" src="x.png"></div>')
    assert _rule14(html).status == "FAIL"


def test_quoted_bracket_inside_attribute_value_does_not_count() -> None:
    # Review round 3: a quoted `]` inside the attribute value would defeat a
    # bracket-first strip -- strings must be stripped before brackets.
    css = _BASE_CSS + ' .x[data-note="].w-82"] { display: block; }'
    html = _doc(css, '<div class="card"><img class="w-82" src="x.png"></div>')
    assert _rule14(html).status == "FAIL"


def test_class_inside_not_or_has_is_a_condition_not_a_definition() -> None:
    # Review round 4: `img:not(.w-82)` styles OTHER imgs; `.x:has(.w-82)`
    # styles `.x` -- neither defines `.w-82`.
    for cond in (".figure img:not(.w-82) { width: 100%; }",
                 ".x:has(.w-82) { display: block; }"):
        html = _doc(_BASE_CSS + " " + cond,
                    '<div class="card"><img class="w-82" src="x.png"></div>')
        assert _rule14(html).status == "FAIL", cond


def test_class_inside_is_where_counts_as_defined() -> None:
    # :is()/:where() arguments DO receive the declarations.
    css = _BASE_CSS + " :is(.w-82, .w-90) { width: 82%; }"
    html = _doc(css, '<div class="card"><img class="w-82" src="x.png"></div>')
    assert _rule14(html).status == "PASS"


def test_definition_must_sit_on_the_selector_subject() -> None:
    # Review round 6: declarations apply to the RIGHTMOST compound only.
    # `.w-82 img` / `.w-82 + .child` / `:is(.w-82 img)` style something
    # ELSE -- none defines the utility.
    for cond in (".w-82 img { width: 82%; }",
                 ".w-82 + .child { width: 82%; }",
                 ":is(.w-82 img) { width: 82%; }"):
        html = _doc(_BASE_CSS + " " + cond,
                    '<div class="card"><img class="w-82" src="x.png"></div>')
        assert _rule14(html).status == "FAIL", cond
    # ...while a descendant-context definition keeps the utility as subject.
    css = _BASE_CSS + " .figure .w-82 { width: 82%; }"
    html = _doc(css, '<div class="card"><img class="w-82" src="x.png"></div>')
    assert _rule14(html).status == "PASS"


def test_unwrap_preserves_compound_boundaries() -> None:
    # Review round 7: `:is(.w-82):hover` is ONE compound whose subject
    # includes .w-82 -- the unwrap must not insert whitespace and split it.
    for defn in (":is(.w-82):hover { width: 82%; }",
                 ":is(.w-82).figure { width: 82%; }",
                 ":nth-child(1 of .w-82):hover { width: 82%; }"):
        html = _doc(_BASE_CSS + " " + defn,
                    '<div class="card"><img class="w-82" src="x.png"></div>')
        assert _rule14(html).status == "PASS", defn


def test_unwrap_preserves_token_boundaries() -> None:
    # Review round 8, the other face of the same coin: `.w-82:is(img)`
    # must not fuse into a `.w-82img` identifier -- the realistic "scope
    # the width utility to media elements" pattern.
    for defn in (".w-82:is(img) { width: 82%; }",
                 ".w-82:is(img, svg) { width: 82%; }",
                 ".w-82:where(img) { width: 82%; }",
                 ".w-82:nth-child(1 of img) { width: 82%; }"):
        html = _doc(_BASE_CSS + " " + defn,
                    '<div class="card"><img class="w-82" src="x.png"></div>')
        assert _rule14(html).status == "PASS", defn


def test_nth_of_selector_list_counts_as_defined() -> None:
    # `:nth-child(1 of .w-82)` DOES style the matching .w-82.
    css = _BASE_CSS + " :nth-child(1 of .w-82) { width: 82%; }"
    html = _doc(css, '<div class="card"><img class="w-82" src="x.png"></div>')
    assert _rule14(html).status == "PASS"


def test_nested_pseudo_classes_resolve_innermost_out() -> None:
    # Review round 5: `:has(:is(.w-82))` styles the :has SUBJECT, not
    # `.w-82` -- the :is unwraps first, then the :has drops it. And
    # `:not(:is(.w-82))` likewise ends up dropped.
    for cond in (".x:has(:is(.w-82)) { display: block; }",
                 ".x img:not(:is(.w-82)) { width: 100%; }"):
        html = _doc(_BASE_CSS + " " + cond,
                    '<div class="card"><img class="w-82" src="x.png"></div>')
        assert _rule14(html).status == "FAIL", cond
    # Documented residual: a double negation (`:not(:not(.w-82))`) DOES
    # select `.w-82`, but rule 14 reads it as a condition and still fails
    # -- define utilities as plain `.class` rules.
    css = _BASE_CSS + " .x img:not(:not(.w-82)) { width: 82%; }"
    html = _doc(css, '<div class="card"><img class="w-82" src="x.png"></div>')
    assert _rule14(html).status == "FAIL"


def test_spacing_and_font_utilities_are_covered() -> None:
    html = _doc(_BASE_CSS,
                '<div class="card"><p class="mt-2 fs-3">text</p></div>')
    r = _rule14(html)
    assert r.status == "FAIL"
    assert "mt-2" in r.detail and "fs-3" in r.detail


def test_non_numeric_classes_are_ignored() -> None:
    # `pb-c` and semantic hooks aren't numeric utilities; rule 14 stays quiet.
    html = _doc(_BASE_CSS,
                '<div class="card pb-c"><p class="band-lede">text</p></div>')
    assert _rule14(html).status == "PASS"


def test_logo_subtree_is_exempt() -> None:
    # Matching rule 13's exemption: vendor logo exports carry arbitrary
    # class names (a tailwind-exported inline SVG could ship `w-3`).
    html = _doc(
        _BASE_CSS,
        '<div data-color-exempt="logo"><svg class="w-3"><rect/></svg></div>',
    )
    assert _rule14(html).status == "PASS"
