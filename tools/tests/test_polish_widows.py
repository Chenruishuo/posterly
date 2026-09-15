"""Browser regression for math tails, width sensitivity and prose coverage."""
from pathlib import Path
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _posterly import polish

FIXTURE = Path(__file__).parent / "fixtures" / "polish_widows.html"


@pytest.fixture(scope="module")
def page():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(timeout=10000)
        page = browser.new_page(viewport={"width": 960, "height": 1920})
        page.emulate_media(media="print")
        page.goto(FIXTURE.as_uri())
        page.evaluate("document.fonts.ready")
        yield page
        browser.close()


def test_four_widows_and_clean_control(page, capsys):
    data = polish.collect_polish_data(page)
    assert page.evaluate(polish._POLISH_JS)["widows"] == data["widows"]
    widows = data["widows"]
    assert len(widows) == 4
    assert {w["cls"].split()[-1] for w in widows} == {
        "inline-math", "fill42", "long-prose", "custom-note",
    }
    assert {w["cls"].split()[-1]: w["frac"] for w in widows} == {
        "inline-math": 19, "fill42": 41, "long-prose": 39, "custom-note": 35,
    }
    assert page.locator(".long-prose").evaluate("el => el.textContent.length") > 220
    polish.report_polish(data, polish.default_polish_args(), FIXTURE)
    out = capsys.readouterr().out
    assert out.index("last-line fill census") > out.rindex("WARN:")
    rows = [ln for ln in out.splitlines() if ln.strip().startswith("n=")]
    assert len(rows) == 5
    assert "inline-math" in rows[0]
    assert "clean-control" in rows[-1]
    assert "95%" in rows[0]


def test_threshold_is_configurable(page):
    data = polish.collect_polish_data(page, widow_fill=0.35)
    assert [w["cls"].split()[-1] for w in data["widows"]] == ["inline-math"]


@pytest.mark.parametrize("markup", [
    '<span class="MathJax" style="display:inline-block;width:90px;height:20px">95%</span>',
    '<math style="display:inline-block;width:90px;height:20px"><mtext>95%</mtext></math>',
])
def test_other_inline_math_roots(page, markup):
    original = page.locator(".math-tail").inner_html()
    try:
        page.locator(".math-tail").evaluate("(el, html) => el.innerHTML = html", markup + ").")
        assert any("inline-math" in w["cls"] for w in polish.collect_polish_data(page)["widows"])
    finally:
        page.locator(".math-tail").evaluate("(el, html) => el.innerHTML = html", original)


@pytest.mark.parametrize("markup", [
    '<mjx-container display="true">95%</mjx-container>',
    '<svg width="90" height="20"><text>95%</text></svg>',
])
def test_display_math_and_media_keep_skip(page, markup):
    original = page.locator(".math-tail").inner_html()
    try:
        page.locator(".math-tail").evaluate("(el, html) => el.innerHTML = html", markup + ").")
        assert not any("inline-math" in w["cls"] for w in polish.collect_polish_data(page)["widows"])
    finally:
        page.locator(".math-tail").evaluate("(el, html) => el.innerHTML = html", original)


def test_generic_multiline_prose_and_short_label_limit(page):
    note = page.locator(".custom-note")
    original = note.inner_html()
    line = "alpha beta gamma delta epsilon zeta eta theta go"
    try:
        # Seven short words on a 40% tail; long, unlisted explanatory prose.
        note.evaluate("(el, text) => el.textContent = text", " ".join([line] * 3) + " a b c d e f tail")
        assert any("custom-note" in w["cls"] for w in polish.collect_polish_data(page)["widows"])
        # The same seven-unit tail on a short two-line label stays conservative.
        note.evaluate("(el, text) => el.textContent = text", line + " a b c d e f tail")
        assert not any("custom-note" in w["cls"] for w in polish.collect_polish_data(page)["widows"])
    finally:
        note.evaluate("(el, html) => el.innerHTML = html", original)


def test_generic_three_words_plus_math_period_is_four_units(page):
    note = page.locator(".custom-note")
    original = note.inner_html()
    try:
        note.evaluate("(el, html) => el.innerHTML = html",
                      'alpha beta gamma delta epsilon zeta eta theta go '
                      'one two six <mjx-container>95%</mjx-container>.')
        assert any("custom-note" in w["cls"] for w in polish.collect_polish_data(page)["widows"])
    finally:
        note.evaluate("(el, html) => el.innerHTML = html", original)


def test_banner_keeps_eighty_percent_even_for_long_prose(page):
    block = page.locator(".clean-control")
    original = block.inner_html()
    line = "alpha beta gamma delta epsilon zeta eta theta go"
    try:
        block.evaluate("(el, text) => { el.classList.add('fb-text'); el.textContent = text; }",
                       " ".join([line] * 9) + " a sufficiently full ending.")
        widows = polish.collect_polish_data(page, widow_fill=0.35)["widows"]
        assert any("clean-control" in w["cls"] and w["banner"] for w in widows)
    finally:
        block.evaluate("(el, html) => { el.classList.remove('fb-text'); el.innerHTML = html; }", original)
