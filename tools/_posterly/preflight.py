"""Static HTML lint — runs before any rendering.

Catches the classes of errors that would otherwise burn a render cycle:

- LaTeX residue (``\\ref{`` / ``\\cite{`` / ``\\textbf{`` / lone ``\\ ``).
- Raw ``<`` inside ``$…$`` / ``$$…$$`` / ``\\(…\\)`` / ``\\[…\\]`` —
  MathJax may HTML-parse it as a tag start depending on its loader mode.
- Local ``src="..."`` images that don't exist on disk.
- Missing or unknown ``data-measure-role`` values.

The line numbers reported by preflight refer to **the original HTML file**.
Earlier versions stripped ``<style>`` / ``<script>`` / ``<!-- … -->``
blocks with ``re.sub(... , "")``, which collapsed newlines and shifted
every subsequent line number by N. We now replace each stripped block
with the SAME NUMBER OF NEWLINES, so character offsets after the strip
still map to the same line in the original file.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


# Roles understood by ``measure`` / ``polish``. Anything outside this
# set in a ``data-measure-role`` attribute is almost certainly a typo
# and would silently be ignored by the geometry pass.
KNOWN_ROLES: set[str] = {
    "poster", "header", "banner", "body",
    "column", "card", "hero", "footer-strip", "footer",
}


# (regex, human description) pairs for LaTeX residue. The patterns are
# scanned over the body with style/script/comments stripped (newline-
# preserved), so each match's character offset still maps to the right
# line in the original file.
LATEX_PATTERNS: list[tuple[str, str]] = [
    (r"\\ref\{",        r"\\ref{...} residue"),
    (r"\\cite\{",       r"\\cite{...} residue"),
    (r"\\textbf\{",     r"\\textbf{...} residue (use <b> or **bold**)"),
    (r"\\textit\{",     r"\\textit{...} residue (use <i> or *italic*)"),
    (r"\\emph\{",       r"\\emph{...} residue"),
    (r"\\section\{",    r"\\section{...} residue"),
    (r"\\label\{",      r"\\label{...} residue"),
    (r"\\begin\{",      r"\\begin{...} residue (use HTML structures)"),
    (r"\\end\{",        r"\\end{...} residue"),
    (r"(?<![\\a-zA-Z])\\\s",
        r"backslash-space '\\ ' (will render literally)"),
]


def _eprint(*args: Any, **kw: Any) -> None:
    print(*args, file=sys.stderr, **kw)


def _newline_preserving_sub(pattern: str, html: str, *,
                            flags: int = 0) -> str:
    """Replace each match with ``\\n`` * <newline-count-in-match>.

    This preserves line numbers across ``<style>`` / ``<script>`` /
    ``<!-- … -->`` blocks so a regex match's character offset in the
    stripped output still maps to the same line in the original file.
    """
    def keep_newlines(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")
    return re.sub(pattern, keep_newlines, html, flags=flags)


def strip_for_lint(html: str) -> str:
    """Remove ``<style>``, ``<script>``, and HTML comments while
    preserving newline counts. The output is what every preflight rule
    scans against.
    """
    html = _newline_preserving_sub(
        r"<style[^>]*>.*?</style>",
        html, flags=re.DOTALL | re.IGNORECASE,
    )
    html = _newline_preserving_sub(
        r"<script[^>]*>.*?</script>",
        html, flags=re.DOTALL | re.IGNORECASE,
    )
    html = _newline_preserving_sub(
        r"<!--.*?-->",
        html, flags=re.DOTALL,
    )
    return html


def find_math_segments(text: str) -> list[tuple[int, int, str]]:
    """Find inline + display math segments. Returns ``[(start, end, body)]``.

    Supports the four delimiter pairs every Claude-poster template
    configures MathJax for:

      - ``$$ … $$`` (display)
      - ``$ … $`` (inline; excludes already-covered ``$$`` regions)
      - ``\\[ … \\]`` (display)
      - ``\\( … \\)`` (inline)
    """
    out: list[tuple[int, int, str]] = []

    def add(s: int, e: int, body: str) -> None:
        out.append((s, e, body))

    # $$...$$
    for m in re.finditer(r"\$\$(.+?)\$\$", text, re.DOTALL):
        add(m.start(), m.end(), m.group(1))
    # \[...\]
    for m in re.finditer(r"\\\[(.+?)\\\]", text, re.DOTALL):
        add(m.start(), m.end(), m.group(1))

    covered = [(s, e) for s, e, _ in out]

    # $...$ — single-line only, not already inside a $$...$$
    for m in re.finditer(r"(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", text):
        s, e = m.start(), m.end()
        if any(cs <= s < ce or cs < e <= ce for cs, ce in covered):
            continue
        add(s, e, m.group(1))
    # \(...\) — single-line only, not already inside a \[...\]
    for m in re.finditer(r"\\\(([^\n]+?)\\\)", text):
        s, e = m.start(), m.end()
        if any(cs <= s < ce or cs < e <= ce for cs, ce in covered):
            continue
        add(s, e, m.group(1))

    return out


def _delim_label(body: str, segment: str) -> str:
    """Try to label a math segment by its delimiter style in error
    output. ``segment`` is the raw matched text; we look at its first
    char(s)."""
    if segment.startswith("$$") and segment.endswith("$$"):
        return "$$...$$"
    if segment.startswith("$") and segment.endswith("$"):
        return "$...$"
    if segment.startswith("\\["):
        return "\\[...\\]"
    if segment.startswith("\\("):
        return "\\(...\\)"
    return "math"


def cmd_preflight(args: argparse.Namespace) -> int:
    html_path = Path(args.html).resolve()
    if not html_path.exists():
        _eprint(f"ERROR: HTML not found: {html_path}")
        return 2
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    body = strip_for_lint(raw)

    problems: list[str] = []
    warnings: list[str] = []

    # 1) LaTeX residue.
    for pat, desc in LATEX_PATTERNS:
        for m in re.finditer(pat, body):
            ln = body[: m.start()].count("\n") + 1
            problems.append(f"L{ln}: {desc} -> '{m.group(0)}'")

    # 2) Raw '<' inside math segments. The common HTML-parse failure
    #    case is `a<b` / `x<y`. We catch '<' even after a letter/digit.
    #    Suppressed only when it's an escape `\<` or part of `</` / `<!`
    #    (HTML constructs MathJax never sees) or `<=` (a single MathJax
    #    token that is parsed atomically and does NOT trip the HTML
    #    tokenizer's tag-start lookahead).
    for s, e, mbody in find_math_segments(body):
        # Compute the math body's offset inside the original segment so
        # multi-line `$$ … \n a < b \n … $$` reports the `<`'s line,
        # not the segment-start line. find_math_segments hands back the
        # full `(start, end, body)` of the segment; the body's first
        # char is at `body[s + (segment_text_len - body_len)]` — easier
        # to recompute via `body.find(mbody, s)`.
        body_offset_in_body = body.find(mbody, s)
        if body_offset_in_body == -1:
            body_offset_in_body = s  # fallback shouldn't happen
        for m in re.finditer(r"(?<!\\)<(?![=/!])", mbody):
            abs_offset = body_offset_in_body + m.start()
            ln = body[: abs_offset].count("\n") + 1
            label = _delim_label(body[s:e], body[s:e])
            problems.append(
                f"L{ln}: raw '<' inside {label} "
                f"'{mbody.strip()[:60]}' -- use \\lt"
            )

    # 3) Image src: local must exist; remote http(s) warns. A print
    #    poster should be self-contained -- a CDN image that 404s or is
    #    slow at render time silently breaks the figure, and the render
    #    gates can't see a missing remote image. data: URIs are inline.
    for m in re.finditer(r'src\s*=\s*["\']([^"\']+)["\']', body):
        src = m.group(1)
        if src.startswith("data:"):
            continue
        if src.startswith(("http://", "https://", "//")):
            ln = body[: m.start()].count("\n") + 1
            warnings.append(
                f"L{ln}: remote image '{src[:60]}' -- inline or localize "
                "it; a print poster should not depend on a CDN at render "
                "time"
            )
            continue
        candidate = (html_path.parent / src).resolve()
        if not candidate.exists():
            ln = body[: m.start()].count("\n") + 1
            problems.append(f"L{ln}: missing local image '{src}'")

    # 4) data-measure-role="poster" required on the root.
    if not re.search(r'data-measure-role\s*=\s*["\']poster["\']', body):
        problems.append(
            'missing required data-measure-role="poster" on root'
        )

    # 5) Unknown role values flag silent measure misses.
    for m in re.finditer(
        r'data-measure-role\s*=\s*["\']([^"\']+)["\']', body
    ):
        role = m.group(1).strip()
        if role not in KNOWN_ROLES:
            ln = body[: m.start()].count("\n") + 1
            problems.append(
                f"L{ln}: unknown data-measure-role='{role}' "
                f"(allowed: {sorted(KNOWN_ROLES)})"
            )

    # 6) Soft sanity: no <title> / no <h1>. Warns, doesn't fail.
    if not re.search(r"<title[^>]*>.+?</title>", raw, re.DOTALL):
        warnings.append("no <title> set")
    if not re.search(r"<h1\b", raw):
        warnings.append(
            "no <h1> -- poster title block usually carries one"
        )

    print(f"[preflight] {html_path}")
    print(f"  problems: {len(problems)}   warnings: {len(warnings)}")
    for w in warnings:
        print(f"  WARN: {w}")
    for p in problems:
        _eprint(f"  FAIL: {p}")

    if problems:
        return 1
    print("[preflight] PASS")
    return 0


def has_required_roles_in_html(html_path: Path) -> dict[str, int]:
    """Cheap static count of each known role on disk. Used by ``polish``
    so it can hard-fail on a poster lacking ALL measurement markup,
    instead of silently PASSing on "0 figures, 0 columns, 0 stat
    elements"."""
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    body = strip_for_lint(raw)
    counts: dict[str, int] = {role: 0 for role in KNOWN_ROLES}
    for m in re.finditer(
        r'data-measure-role\s*=\s*["\']([^"\']+)["\']', body
    ):
        role = m.group(1).strip()
        if role in counts:
            counts[role] += 1
    return counts
