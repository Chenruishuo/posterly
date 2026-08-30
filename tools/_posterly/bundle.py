"""Freeze a poster into ONE self-contained HTML file (``bundle``).

The authoring workspace is a *directory*: ``poster.html`` sits next to
``images/`` and -- when the Axis 4 voice is off the style-gate
whitelist -- a vendored ``fonts/`` of static woff2 files. Every gate
runs inside that directory, so nothing in the Step 4 loop ever notices
that the HTML *alone* is incomplete. The moment the file leaves the
directory (mailed to a co-author, handed to a print shop, delivered to
a customer) every ``<img src>``, every CSS ``url()`` and every
``@font-face`` resolves to nothing: the poster opens as a skeleton of
alt-text boxes set in fallback faces.

``bundle`` freezes the directory into the file. Local ``src=`` and
``url()`` references become ``data:`` URIs, and the MathJax CDN
``<script>`` is replaced by the skill's own bundled ``tex-svg.js``,
inline. The result needs no sibling files and no network -- and stays
**editable**: the prose, the CSS and the TeX are all still source.
That is the whole point. A recipient can edit the copy they were sent
and re-render it (``render_preview.py``, or any headless-Chromium PDF
print with the CSS page size honoured) and get the same sheet back.

Run it **last, on a green poster**, and keep the workspace copy as the
working file: the bundle is a delivery artifact, not a new editing base
for the measure loop. A multi-MB single file is slow to Grep and slow
to Edit, and the gates gain nothing from it.

What "self-contained" is *checked* to mean: after rewriting, no
reference to anything outside the file remains. Anything that cannot be
inlined -- a missing local file, a remote http(s) image, a
``<link rel="stylesheet">`` -- is a HARD failure (exit 1) and no output
is written. A bundle that is silently still-broken is worse than no
bundle: it looks finished. ``--allow-remote`` downgrades the remote
case to a warning for the deliberate exception (a poster that genuinely
wants a live URL).

Honest limits:

  * Inlining is byte-for-byte, so a figure referenced twice is embedded
    twice. The report names every reference used more than once, with
    its size, so an outsized duplicate can be hoisted by hand.
  * An inlined SVG that itself references an external file (a rare
    matplotlib export with a linked raster) is embedded as-is: its
    inner reference is not followed, and the self-containment check
    cannot see it.
  * MathJax is inlined whenever the CDN tag is present, math or not
    (~2 MB) -- whether any TeX will actually typeset is not knowable
    statically. Delete the tag first for a math-free poster.
  * base64 costs ~33% over the raw bytes. That is the price of one
    file; it does not change what Chromium rasterizes.
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import render
from .textutil import ascii_safe

EXIT_USAGE = 2

#: MIME types for the extensions the poster contract actually uses.
#: ``mimetypes`` is the fallback, but it does not know ``woff2`` on
#: every platform -- and a vendored-font poster is exactly the case
#: that depends on getting that one right.
_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".js": "text/javascript",
    ".css": "text/css",
}

#: ``src="…"`` on any element. The lookbehind pins it to a real
#: attribute boundary so ``data-src=`` (and any other ``…src=`` suffix)
#: is not rewritten by accident -- ``\bsrc`` would match inside it,
#: because ``-`` is a word boundary.
_SRC_RE = re.compile(r'(?<=[\s"\'])(src\s*=\s*)(["\'])([^"\']*)\2', re.IGNORECASE)

#: CSS ``url(…)``, quoted or bare. A quoted URL may legally contain a
#: parenthesis; only the bare form stops at the first ``)``.
_URL_RE = re.compile(
    r'url\(\s*(?:"(?P<double>[^"]*)"|\'(?P<single>[^\']*)\'|' r"(?P<bare>[^)]*?))\s*\)",
    re.IGNORECASE,
)

#: Regions that contain examples or program text, not live resource
#: references. HTML comments are common in the shipped templates (including
#: commented-out ``<img src=...>`` examples), and ``src=`` / ``url(…)``
#: inside an inline script is JavaScript string data. CSS comments are inert
#: too. Opening ``<script>`` tags stay rewriteable so a real local ``src`` on
#: the element itself can still be bundled.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_INERT_RE = re.compile(
    r"<!--.*?-->|<script\b[^>]*>.*?</script\s*>|/\*.*?\*/",
    re.IGNORECASE | re.DOTALL,
)

#: ``<link rel="stylesheet">`` -- off the poster contract (the
#: templates inline all CSS) and deliberately NOT inlined: it is
#: reported, so a poster that grew one fails loudly instead of shipping
#: a bundle that is missing its stylesheet.
_LINK_CSS_RE = re.compile(
    r'<link\b[^>]*?\brel\s*=\s*["\']?stylesheet["\']?[^>]*>', re.IGNORECASE
)

#: Any ``<script src="…"></script>``. Matched as tag + closer so the
#: replacement can drop ``src`` and carry the runtime as element text.
#: Which of these is actually the MathJax CDN is decided by
#: ``render._MATHJAX_CDN_RE``, not by this pattern.
_SCRIPT_SRC_RE = re.compile(
    r'<script\b(?P<pre>[^>]*?)(?<=[\s"\'])src\s*=\s*'
    r'(?P<q>["\'])(?P<url>[^"\']*)(?P=q)(?P<post>[^>]*)>\s*</script\s*>',
    re.IGNORECASE,
)

#: Stands in for the MathJax runtime until every reference check passes.
#: Keeping the ~2 MB payload out of the intermediate document makes it
#: impossible to return a half-built runtime when another dependency fails.
_MATHJAX_SLOT = "@@POSTERLY_MATHJAX_RUNTIME@@"

_BANNER = """<!-- posterly: SELF-CONTAINED BUNDLE.
     Images and fonts are inlined as data: URIs; the MathJax runtime is
     inline script text. This file needs no sibling files and no network.
     The prose, the CSS and the TeX are still source: edit them here, then
     re-render to PDF with headless Chromium honouring the CSS page
     size, e.g.  python tools/render_preview.py <this file>
     A browser's own print dialog is NOT equivalent -- page size,
     margins and background graphics all have to be set by hand, and
     a poster canvas is rarely an offerable paper size. -->"""

_REMOTE_BANNER = """<!-- posterly: BUNDLE WITH REMOTE REFERENCES.
     Local images and fonts are data: URIs and the MathJax runtime is
     inline, but resources deliberately kept by --allow-remote still need
     a network.
     The prose, the CSS and the TeX remain editable source. -->"""


class BundleReport:
    """What was inlined, and what could not be."""

    def __init__(self) -> None:
        #: ref -> (times seen, source bytes each)
        self.inlined: dict[str, tuple[int, int]] = {}
        self.missing: list[str] = []
        self.remote: list[str] = []
        self.problems: list[str] = []
        self.mathjax_bytes = 0

    def count(self, ref: str, size: int) -> None:
        seen, _ = self.inlined.get(ref, (0, size))
        self.inlined[ref] = (seen + 1, size)

    @property
    def source_bytes(self) -> int:
        return sum(n * size for n, size in self.inlined.values())

    @property
    def duplicates(self) -> list[tuple[str, int, int]]:
        return sorted(
            ((ref, n, size) for ref, (n, size) in self.inlined.items() if n > 1),
            key=lambda t: -t[1] * t[2],
        )


def _skip_ref(ref: str) -> bool:
    """References the rewriter must leave exactly as they are: an
    already-inline ``data:`` URI (so a second run is a no-op) and a
    same-document fragment -- ``url(#psReg)`` is the identity glyph's
    SVG paint reference, not a file."""
    r = ref.strip().lower()
    return (not r) or r.startswith(("data:", "#", "about:", "blob:"))


def _is_remote(ref: str) -> bool:
    """True for anything the bundler cannot read off the local disk:
    a protocol-relative ``//host/…`` and any explicit scheme
    (``http:``, ``https:``, but also ``file:`` / ``ftp:`` -- absolute
    URLs are not portable inside a delivered file either)."""
    r = ref.strip()
    return r.startswith("//") or bool(urlsplit(r).scheme)


def _resolve_local(ref: str, base_dir: Path) -> Path:
    """Strip ``?query`` / ``#fragment`` and percent-decode before
    resolving. ``fig.png?v=2`` and ``my%20fig.png`` are both real, and
    both read as missing files if taken literally -- the same rule
    ``preflight`` uses to find missing local images."""
    return base_dir / unquote(urlsplit(ref).path)


def _data_uri(path: Path) -> str:
    ext = path.suffix.lower()
    mime = (
        _MIME_BY_EXT.get(ext)
        or mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _inline_ref(
    ref: str,
    base_dir: Path,
    report: BundleReport,
    cache: dict[str, str],
) -> str | None:
    """Return the ``data:`` URI replacing ``ref``, or None to leave the
    reference untouched (already inline, a fragment, or unresolvable --
    in which case it is recorded on the report)."""
    if _skip_ref(ref):
        return None
    if _is_remote(ref):
        report.remote.append(ref)
        return None
    path = _resolve_local(ref, base_dir)
    if not path.is_file():
        report.missing.append(ref)
        return None
    key = str(path.resolve())
    if key not in cache:
        cache[key] = _data_uri(path)
    report.count(ref, path.stat().st_size)
    return cache[key]


def inline_references(text: str, base_dir: Path, report: BundleReport) -> str:
    """Rewrite every local ``src=`` and CSS ``url(…)`` in ``text`` to a
    ``data:`` URI. One cache keyed by resolved path, so a file
    referenced twice is read and encoded once (the *output* still
    carries both copies -- see the duplicates report)."""
    cache: dict[str, str] = {}

    def _sub_src(m: re.Match[str]) -> str:
        uri = _inline_ref(m.group(3), base_dir, report, cache)
        if uri is None:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{uri}{m.group(2)}"

    def _sub_url(m: re.Match[str]) -> str:
        if m.group("double") is not None:
            ref, quote = m.group("double"), '"'
        elif m.group("single") is not None:
            ref, quote = m.group("single"), "'"
        else:
            ref, quote = m.group("bare"), '"'
        uri = _inline_ref(ref, base_dir, report, cache)
        if uri is None:
            return m.group(0)
        # A base64 data: URI holds no quote or paren, so re-quoting is
        # always safe -- and quoting a bare url() keeps a long payload
        # from tripping CSS's unquoted-url charset rules.
        return f"url({quote}{uri}{quote})"

    def _rewrite_active(fragment: str) -> str:
        fragment = _SRC_RE.sub(_sub_src, fragment)
        return _URL_RE.sub(_sub_url, fragment)

    pieces: list[str] = []
    end = 0
    for match in _INERT_RE.finditer(text):
        pieces.append(_rewrite_active(text[end : match.start()]))
        inert = match.group(0)
        if inert.lower().startswith("<script"):
            # Rewrite a real ``src`` on the opening tag, but never scan the
            # JavaScript body for strings that merely look like HTML/CSS.
            tag_end = inert.find(">") + 1
            pieces.append(_SRC_RE.sub(_sub_src, inert[:tag_end]) + inert[tag_end:])
        else:
            pieces.append(inert)
        end = match.end()
    pieces.append(_rewrite_active(text[end:]))
    return "".join(pieces)


def extract_mathjax(text: str, report: BundleReport) -> tuple[str, str]:
    """Swap the MathJax CDN ``<script src=…>`` for a placeholder and
    return ``(text, runtime_js)``.

    Only the CDN shape the templates emit is touched -- the match is
    ``render._MATHJAX_CDN_RE``, deliberately shared with the render
    gates so the bundle inlines exactly the file those gates route to.
    A poster that vendored its own local copy keeps it (the ordinary
    ``src=`` pass turns that into a data: URI), and a future
    ``mathjax@4`` URL is not silently downgraded to the bundled 3.x.

    ``runtime_js`` is empty when there is nothing to inline; the CDN
    reference is then left in place and the self-containment check
    fails on it, which is the honest outcome.
    """
    mj = render.bundled_mathjax_path()
    runtime: list[str] = []

    def _sub(m: re.Match[str]) -> str:
        if not render._MATHJAX_CDN_RE.match(m.group("url").strip()):
            return m.group(0)
        if mj is None:
            report.problems.append(
                "MathJax CDN <script> found but the skill's bundled "
                "assets/mathjax/tex-svg.js is missing -- cannot inline "
                "the math runtime"
            )
            return m.group(0)
        js = mj.read_text(encoding="utf-8")
        if "</script" in js.lower():
            # An inline <script> element ends at the first "</script"
            # in its text, wherever it sits -- so this would truncate
            # the runtime mid-file and the math would silently vanish.
            report.problems.append(
                f"bundled MathJax ({ascii_safe(mj)}) contains a literal "
                "'</script' and cannot be inlined verbatim"
            )
            return m.group(0)
        runtime.append(js)
        attrs = f"{m.group('pre')} {m.group('post')}".strip()
        attrs = f" {attrs}" if attrs else ""
        return f"<script{attrs}>{_MATHJAX_SLOT}</script>"

    if _MATHJAX_SLOT in text:
        report.problems.append(
            f"poster already contains the reserved marker "
            f"{_MATHJAX_SLOT} -- cannot bundle safely"
        )
        return text, ""
    # A commented-out MathJax example is documentation, not a live runtime.
    pieces: list[str] = []
    end = 0
    for comment in _HTML_COMMENT_RE.finditer(text):
        pieces.append(_SCRIPT_SRC_RE.sub(_sub, text[end : comment.start()]))
        pieces.append(comment.group(0))
        end = comment.end()
    pieces.append(_SCRIPT_SRC_RE.sub(_sub, text[end:]))
    text = "".join(pieces)
    js = runtime[0] if runtime else ""
    report.mathjax_bytes = len(js.encode("utf-8"))
    return text, js


def _insert_banner(text: str, *, has_remote: bool = False) -> str:
    """Put the delivery banner right after the doctype (it must stay
    first), else at the very top."""
    banner = _REMOTE_BANNER if has_remote else _BANNER
    m = re.match(r"\s*<!DOCTYPE[^>]*>", text, re.IGNORECASE)
    if m:
        return f"{text[:m.end()]}\n{banner}{text[m.end():]}"
    return f"{banner}\n{text}"


def bundle_html(
    html_path: Path, report: BundleReport, allow_remote: bool = False
) -> str | None:
    """Build the requested delivery document.

    Returns None on a hard problem. With ``allow_remote``, a document with
    reported remote dependencies is returned deliberately.
    """
    text = html_path.read_text(encoding="utf-8", errors="ignore")

    uncommented = _HTML_COMMENT_RE.sub("", text)
    for m in _LINK_CSS_RE.finditer(uncommented):
        report.problems.append(
            f'<link rel="stylesheet"> is not inlined: '
            f"'{ascii_safe(m.group(0)[:80])}' -- the poster contract "
            "keeps all CSS in a <style> block; move it inline and "
            "re-run"
        )

    text, runtime = extract_mathjax(text, report)
    text = inline_references(text, html_path.parent, report)

    for ref in report.missing:
        report.problems.append(
            f"missing local file '{ascii_safe(ref)}' -- cannot inline"
        )
    if report.remote and not allow_remote:
        for ref in report.remote:
            report.problems.append(
                f"remote reference '{ascii_safe(ref[:80])}' -- a bundle "
                "cannot fetch it; localize the file (or pass "
                "--allow-remote to ship the dependency deliberately)"
            )

    if report.problems:
        return None

    if runtime:
        text = text.replace(_MATHJAX_SLOT, runtime)
    return _insert_banner(text, has_remote=bool(report.remote))


def _mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def cmd_bundle(args: argparse.Namespace) -> int:
    html_path = Path(args.html)
    if not html_path.is_file():
        print(f"[bundle] FAIL: no such file: {ascii_safe(html_path)}", file=sys.stderr)
        return EXIT_USAGE

    out_path = (
        Path(args.out)
        if args.out
        else html_path.with_name(f"{html_path.stem}_standalone.html")
    )
    if out_path.resolve() == html_path.resolve():
        # The workspace copy is the editing base for the whole measure
        # loop; a multi-MB bundle overwriting it costs the poster.
        print(
            "[bundle] FAIL: refusing to overwrite the input -- the "
            "workspace poster.html stays the working file; write the "
            "bundle elsewhere with -o",
            file=sys.stderr,
        )
        return EXIT_USAGE

    report = BundleReport()
    result = bundle_html(html_path, report, allow_remote=args.allow_remote)

    print(f"[bundle] {ascii_safe(html_path)} -> {ascii_safe(out_path)}")
    refs = sum(n for n, _ in report.inlined.values())
    print(
        f"  inlined:  {refs} reference(s) from "
        f"{len(report.inlined)} file(s), {_mb(report.source_bytes)} "
        f"of source"
    )
    if report.mathjax_bytes:
        print(
            f"  mathjax:  bundled tex-svg.js inlined " f"({_mb(report.mathjax_bytes)})"
        )
    for ref, n, size in report.duplicates:
        print(
            f"  WARN: '{ascii_safe(ref)}' inlined {n}x "
            f"({_mb(size)} each) -- hoist it to a CSS variable or a "
            f"single element if the size matters"
        )
    if args.allow_remote:
        for ref in report.remote:
            print(
                f"  WARN: remote reference kept: "
                f"'{ascii_safe(ref[:80])}' -- this bundle is NOT "
                f"self-contained"
            )

    if result is None:
        for p in report.problems:
            print(f"  FAIL: {p}", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result, encoding="utf-8")
    print(f"  output:   {_mb(len(result.encode('utf-8')))}")
    if report.remote:
        print(
            "[bundle] PASS -- bundle written; NOT self-contained "
            "(remote references kept by --allow-remote)"
        )
    else:
        print("[bundle] PASS -- self-contained " "(no external references remain)")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    """Standalone entry point (the real wiring is in poster_check.py)."""
    p = argparse.ArgumentParser(prog="bundle", description=__doc__)
    p.add_argument("html")
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--allow-remote", action="store_true")
    return p


if __name__ == "__main__":
    sys.exit(cmd_bundle(build_arg_parser().parse_args()))
