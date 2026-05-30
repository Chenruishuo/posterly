"""Preflight: math delimiter coverage, line-number preservation, role
counting. Pure-static checks — no Playwright needed."""
from __future__ import annotations

import re

from _posterly import preflight


# ---- math delimiters -------------------------------------------------------

def _math_bodies(text: str) -> set[str]:
    """Strip surrounding whitespace inside the returned bodies so the
    parametrised assertions are insensitive to padding."""
    return {body.strip() for _s, _e, body in preflight.find_math_segments(text)}


def test_dollar_inline_math() -> None:
    text = "Energy is $E = mc^2$ in flat space."
    assert "E = mc^2" in _math_bodies(text)


def test_dollar_dollar_display_math() -> None:
    text = "Display: $$\\sum_i x_i$$ end."
    assert "\\sum_i x_i" in _math_bodies(text)


def test_paren_inline_math() -> None:
    text = "Inline \\(a^2 + b^2 = c^2\\) end."
    assert "a^2 + b^2 = c^2" in _math_bodies(text)


def test_bracket_display_math() -> None:
    text = "Display \\[\\int_0^1 x\\,dx\\] end."
    assert "\\int_0^1 x\\,dx" in _math_bodies(text)


def test_raw_lt_in_multiline_display_math_reports_correct_line(tmp_path) -> None:
    """Codex regression: previously the line-number was taken from the
    segment start, so `$$\\n  a < b\\n$$` reported L1 when `<` was on L2.
    Now it must report the actual line of the `<`."""
    import argparse as _ap
    p = tmp_path / "p.html"
    p.write_text(
        '<html><body>\n'                                  # L1
        '  <div data-measure-role="poster">\n'            # L2
        '    <p>before</p>\n'                              # L3
        '    $$\n'                                         # L4
        '      a < b\n'                                    # L5  ← `<` here
        '    $$\n'                                         # L6
        '  </div>\n'                                      # L7
        '</body></html>\n',                                # L8
        encoding="utf-8",
    )
    import io, contextlib
    args = _ap.Namespace(html=str(p))
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        preflight.cmd_preflight(args)
    err_text = err.getvalue()
    assert "L5:" in err_text, (
        f"expected the raw-'<' error to point at L5 (the line "
        f"with `a < b`), got stderr: {err_text!r}"
    )


def test_nested_inline_inside_display_not_double_counted() -> None:
    """``$$a$b$$`` should produce ONE segment, not three. (Inline
    ``$...$`` lookahead skips ranges already covered by ``$$...$$``.)"""
    text = "Outer: $$a$b$$ end"
    bodies = _math_bodies(text)
    assert any("a" in b and "b" in b for b in bodies)
    assert "a" not in bodies  # the lone-`a` inline should NOT appear


# ---- newline-preserving strip ----------------------------------------------

def test_strip_preserves_line_numbers_across_style_block() -> None:
    """A multi-line <style> block must be replaced with the SAME number
    of newlines so character offsets after the strip still map to the
    right line in the original."""
    html = (
        "<html>\n"            # L1
        "<head>\n"            # L2
        "<style>\n"           # L3
        "  body {\n"          # L4
        "    color: red;\n"   # L5
        "  }\n"               # L6
        "</style>\n"          # L7
        "</head>\n"           # L8
        "<body>MARKER</body>\n"  # L9
        "</html>\n"
    )
    stripped = preflight.strip_for_lint(html)
    idx = stripped.index("MARKER")
    line = stripped[: idx].count("\n") + 1
    assert line == 9, (
        f"expected MARKER on line 9 (newline-preserved), got {line}; "
        f"stripped output is {stripped!r}"
    )


def test_strip_preserves_line_numbers_across_script_and_comments() -> None:
    html = (
        "<html>\n"                                                  # L1
        "<script>\n"                                                # L2
        "  const x = 1;\n"                                          # L3
        "  const y = 2;\n"                                          # L4
        "</script>\n"                                               # L5
        "<!-- a multi-line\n     HTML comment -->\n"                # L6,L7
        "<body>MARKER</body>\n"                                     # L8
    )
    stripped = preflight.strip_for_lint(html)
    idx = stripped.index("MARKER")
    line = stripped[: idx].count("\n") + 1
    assert line == 8


# ---- role counting ---------------------------------------------------------

def test_role_counts_static(tmp_path) -> None:
    p = tmp_path / "p.html"
    p.write_text(
        """<html><body>
          <div data-measure-role="poster">
            <div data-measure-role="header"></div>
            <div data-measure-role="body">
              <div data-measure-role="column">
                <div data-measure-role="card"></div>
                <div data-measure-role="card"></div>
              </div>
              <div data-measure-role="column">
                <div data-measure-role="card"></div>
              </div>
            </div>
            <div data-measure-role="footer"></div>
          </div>
        </body></html>""",
        encoding="utf-8",
    )
    counts = preflight.has_required_roles_in_html(p)
    assert counts["poster"] == 1
    assert counts["header"] == 1
    assert counts["body"] == 1
    assert counts["column"] == 2
    assert counts["card"] == 3
    assert counts["footer"] == 1
    assert counts["footer-strip"] == 0  # absent → zero, not raised


def test_role_counts_ignore_unknown(tmp_path) -> None:
    p = tmp_path / "p.html"
    p.write_text(
        '<div data-measure-role="poster"></div>'
        '<div data-measure-role="bogus-role"></div>',
        encoding="utf-8",
    )
    counts = preflight.has_required_roles_in_html(p)
    assert counts["poster"] == 1
    assert "bogus-role" not in counts


# ---- LaTeX residue patterns ------------------------------------------------

def test_latex_residue_patterns_cover_common_cases() -> None:
    """Spot-check the LATEX_PATTERNS table catches what it should."""
    cases = {
        "\\ref{fig:a}":   r"\\ref\{",
        "\\cite{kim24}":  r"\\cite\{",
        "\\textbf{bold}": r"\\textbf\{",
        "\\section{X}":   r"\\section\{",
        "\\begin{eq}":    r"\\begin\{",
    }
    pats = {pat: desc for pat, desc in preflight.LATEX_PATTERNS}
    for sample, expected_pat in cases.items():
        assert expected_pat in pats, (
            f"LATEX_PATTERNS missing rule for {expected_pat!r}"
        )
        assert re.search(expected_pat, sample) is not None, (
            f"pattern {expected_pat!r} fails to match {sample!r}"
        )


# ---- end-to-end on the hello_world example ---------------------------------

def test_hello_world_preflight_passes() -> None:
    """The shipped hello_world example MUST pass preflight cleanly —
    it's the install-verification fixture."""
    import argparse as _ap

    from pathlib import Path
    hello = (Path(__file__).resolve().parent.parent
             / "examples" / "hello_world" / "poster.html")
    assert hello.exists(), f"hello_world poster missing at {hello}"
    args = _ap.Namespace(html=str(hello))
    rc = preflight.cmd_preflight(args)
    assert rc == 0


# ---- image src handling ----------------------------------------------------

def test_remote_image_warns_not_fails(tmp_path, capsys) -> None:
    """A print poster should be self-contained: a remote <img> WARNS
    (soft) but does not fail preflight; an inline data: URI is silent."""
    import argparse as _ap
    p = tmp_path / "p.html"
    p.write_text(
        '<html><body><div data-measure-role="poster">'
        '<img src="https://cdn.example.com/fig.png">'
        '<img src="data:image/png;base64,AAAA">'
        '</div></body></html>',
        encoding="utf-8",
    )
    rc = preflight.cmd_preflight(_ap.Namespace(html=str(p)))
    out = capsys.readouterr().out
    assert rc == 0, "remote image is a warning, not a hard failure"
    assert out.count("remote image") == 1, "only the http img, not data:"


def test_missing_local_image_still_fails(tmp_path, capsys) -> None:
    import argparse as _ap
    p = tmp_path / "p.html"
    p.write_text(
        '<html><body><div data-measure-role="poster">'
        '<img src="nope.png"></div></body></html>',
        encoding="utf-8",
    )
    rc = preflight.cmd_preflight(_ap.Namespace(html=str(p)))
    assert rc == 1
    assert "missing local image" in capsys.readouterr().err
