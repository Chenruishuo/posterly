"""Tests for the role-nesting structure check in ``preflight``.

Why this exists: a misplaced ``</div>`` closes ``.poster`` early so
``footer-strip`` / ``footer`` end up outside the grid. The browser
tolerates the unbalanced markup; the CSS template's grid-template-rows
collapses two rows to 0 px without complaint; ``measure`` reports the
footer-strip rendered at viewport-bottom (off-canvas) without surfacing
the actual cause. This gate turns that silent failure into a preflight
problem pointing at the role whose parent went wrong.

The rule is intentionally narrow: each role must sit under its required
parent role per ``ROLE_PARENTS``. We do NOT enforce stray-close
detection (HTMLParser's recovery and the browser's eagerly rebalance in
ways that mask which ``</tag>`` was actually misplaced), and we do NOT
re-check role *presence* (``measure`` already hard-fails on missing
``body`` / ``column``-or-``hero`` at render time, and a duplicate static
rule would over-strict the minimal fixtures used to test other
preflight rules in isolation).
"""
from __future__ import annotations

import argparse
import io
import contextlib

from _posterly import preflight
from _posterly.preflight import check_role_nesting


# ---- pure-function checker: parent-role detection ------------------------


def test_nesting_walker_records_parent_role_per_node() -> None:
    """Every role-bearing element knows the *nearest* role-bearing
    ancestor. Non-role wrappers (``div``, ``section``) are transparent
    -- the parent role is the next role-bearing div above, not the
    immediate DOM parent."""
    html = (
        '<div data-measure-role="poster">\n'
        '  <header data-measure-role="header"><h1>x</h1></header>\n'
        '  <div data-measure-role="body">\n'
        '    <div data-measure-role="column">\n'
        '      <div class="wrapper">\n'           # transparent wrapper
        '        <div data-measure-role="card">card</div>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'
    )
    roles, _stray = check_role_nesting(html)
    parents = {r: p for r, p, _ln, _t in roles}
    assert parents == {
        "poster": None,
        "header": "poster",
        "body": "poster",
        "column": "body",
        "card": "column",  # transparent .wrapper is skipped
    }


def test_void_tags_do_not_inflate_the_stack() -> None:
    """``<br>`` / ``<img>`` / ``<meta>`` have no end tag in HTML5; the
    walker must not push them or every doc with self-closing void
    elements would corrupt parent-role tracking."""
    html = (
        '<div data-measure-role="poster">\n'
        '  <div data-measure-role="body">\n'
        '    <img src="x.png">\n'              # void; no </img>
        '    <br>\n'                            # void
        '    <div data-measure-role="column">col</div>\n'
        '  </div>\n'
        '</div>\n'
    )
    roles, _stray = check_role_nesting(html)
    parents = {r: p for r, p, _ln, _t in roles}
    # If void tags were pushed onto the stack, ``column`` would report
    # parent ``br`` (or no role) instead of ``body``.
    assert parents["column"] == "body"


# ---- end-to-end: cmd_preflight surfaces the structure problems -----------


def _run(html: str, tmp_path) -> tuple[int, str, str]:
    """Helper: write ``html`` to disk, run ``cmd_preflight``, capture
    rc + stdout + stderr."""
    p = tmp_path / "p.html"
    p.write_text(html, encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = preflight.cmd_preflight(argparse.Namespace(html=str(p)))
    return rc, out.getvalue(), err.getvalue()


def test_card_directly_under_body_fails(tmp_path) -> None:
    """``card`` must sit inside a ``column`` or ``hero`` -- a card
    directly under ``body`` (often from a misplaced ``</div>`` that
    closed the column early) is the silent-misalignment trigger."""
    html = (
        '<html><body>\n'
        '<div data-measure-role="poster">\n'
        '  <div data-measure-role="body">\n'
        '    <div data-measure-role="card">orphan card</div>\n'
        '  </div>\n'
        '</div>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run(html, tmp_path)
    assert rc == 1
    assert "data-measure-role='card'" in err
    # The error names the actual offending parent so the user can grep
    # the file with one click.
    assert "inside body" in err


def test_footer_strip_outside_poster_fails(tmp_path) -> None:
    """If a ``</div>`` closes ``.poster`` early, a later ``footer-strip``
    sits at document root. The grid template's auto rows would collapse
    silently; preflight must catch it as a parent-role mismatch."""
    html = (
        '<html><body>\n'
        '<div data-measure-role="poster">\n'
        '  <div data-measure-role="header"><h1>x</h1></div>\n'
        '  <div data-measure-role="body">\n'
        '    <div data-measure-role="column">\n'
        '      <div data-measure-role="card">c</div>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'                              # closes poster early
        '<section data-measure-role="footer-strip">strip</section>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run(html, tmp_path)
    assert rc == 1
    assert "footer-strip" in err
    assert "(document root)" in err


def test_extra_close_div_real_world_repro_fails(tmp_path) -> None:
    """Real-world reproducer: a stray ``</div>`` inside ``body`` ends
    up closing ``.poster`` early once HTMLParser rebalances, so the
    ``footer-strip`` after it lands outside the poster grid. The
    browser tolerated this and ``measure`` reported the strip top
    off-canvas; the parent-role check below names it directly."""
    html = (
        '<html><body>\n'
        '<div data-measure-role="poster">\n'
        '  <div data-measure-role="body">\n'
        '    <div data-measure-role="column">\n'
        '      <div data-measure-role="card">a</div>\n'
        '    </div>\n'                                 # closes col
        '    </div>\n'                                 # extra close
        '  </div>\n'                                   # closes body...
        '  <section data-measure-role="footer-strip">f</section>\n'
        '</div>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run(html, tmp_path)
    assert rc == 1
    # The footer-strip ends up outside `.poster` once the rebalance
    # consumes the extra `</div>`. That's the symptom that previously
    # cost ~half an hour of off-canvas measure debugging.
    assert "footer-strip" in err


def test_well_nested_real_template_passes(tmp_path) -> None:
    """The shipped 4-column landscape structure must not trip the new
    rule. (Smoke check on the structural shape, not full content.)"""
    html = (
        '<!DOCTYPE html><html><head><title>x</title></head><body>\n'
        '<div data-measure-role="poster">\n'
        '  <header data-measure-role="header"><h1>title</h1></header>\n'
        '  <section data-measure-role="banner">tldr</section>\n'
        '  <div data-measure-role="body">\n'
        '    <div data-measure-role="column">\n'
        '      <div data-measure-role="card">c1</div>\n'
        '      <div data-measure-role="card">c2</div>\n'
        '    </div>\n'
        '    <div data-measure-role="column">\n'
        '      <div data-measure-role="card">c3</div>\n'
        '    </div>\n'
        '  </div>\n'
        '  <section data-measure-role="footer-strip">strip</section>\n'
        '  <div data-measure-role="footer">f</div>\n'
        '</div>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run(html, tmp_path)
    assert rc == 0, f"expected PASS on a well-nested template, got: {err!r}"
    assert "expected parent role" not in err


def test_hero_template_card_under_hero_passes(tmp_path) -> None:
    """``card`` is allowed under ``hero`` (per the landscape_hero
    template), not just ``column``."""
    html = (
        '<!DOCTYPE html><html><head><title>x</title></head><body>\n'
        '<div data-measure-role="poster">\n'
        '  <header data-measure-role="header"><h1>t</h1></header>\n'
        '  <div data-measure-role="body">\n'
        '    <section data-measure-role="hero">\n'
        '      <div data-measure-role="card">hero card</div>\n'
        '    </section>\n'
        '    <div data-measure-role="column">\n'
        '      <div data-measure-role="card">side</div>\n'
        '    </div>\n'
        '  </div>\n'
        '  <div data-measure-role="footer">f</div>\n'
        '</div>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run(html, tmp_path)
    assert rc == 0, f"expected PASS, got: {err!r}"


def test_body_less_layout_column_under_poster_passes(tmp_path) -> None:
    """``body`` has never been *required* by any gate -- ``measure``
    doesn't read it and ``preflight``/``polish`` only require presence
    for ``poster``/``column``/``card``. A poster hanging its columns
    (or ``hero``) directly off the poster root is valid today and must
    not be retroactively rejected by the nesting rule."""
    html = (
        '<!DOCTYPE html><html><head><title>x</title></head><body>\n'
        '<div data-measure-role="poster">\n'
        '  <header data-measure-role="header"><h1>t</h1></header>\n'
        '  <div data-measure-role="column">\n'
        '    <div data-measure-role="card">c</div>\n'
        '  </div>\n'
        '  <section data-measure-role="hero">\n'
        '    <div data-measure-role="card">h</div>\n'
        '  </section>\n'
        '  <section data-measure-role="footer-strip">strip</section>\n'
        '</div>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run(html, tmp_path)
    assert rc == 0, f"expected PASS on a body-less layout, got: {err!r}"


def test_footer_strip_inside_body_passes(tmp_path) -> None:
    """A hand-rolled layout may nest the strip/footer inside ``body``
    instead of as a direct poster grid row; measure reads the strip's
    rendered position regardless. Only the *document root* escape (the
    precipitating stray-``</div>`` bug) must keep failing -- pinned by
    ``test_footer_strip_outside_poster_fails`` above."""
    html = (
        '<!DOCTYPE html><html><head><title>x</title></head><body>\n'
        '<div data-measure-role="poster">\n'
        '  <header data-measure-role="header"><h1>t</h1></header>\n'
        '  <div data-measure-role="body">\n'
        '    <div data-measure-role="column">\n'
        '      <div data-measure-role="card">c</div>\n'
        '    </div>\n'
        '    <section data-measure-role="footer-strip">strip</section>\n'
        '    <div data-measure-role="footer">f</div>\n'
        '  </div>\n'
        '</div>\n'
        '</body></html>\n'
    )
    rc, _out, err = _run(html, tmp_path)
    assert rc == 0, f"expected PASS with strip/footer inside body, got: {err!r}"
