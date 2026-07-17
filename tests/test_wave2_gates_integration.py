"""Chromium-gated integration tests for the wave-2 gate additions in
``polish``'s ``_POLISH_JS``: generic (unlisted-class) WIDOW discovery,
GLUE-CHAIN, the TEXT-WRAP census, TRACK/INNER-VOID, and the composed
CONTRAST gate.

Each fixture pins a failure mode found either in the wave-2 posters or in
the external review of the gate code itself:

  * generic widow: a custom-class block (no whitelisted prose class) whose
    last line is a stranded single word must flag -- INCLUDING when the
    paragraph contains an early ``display:inline-block`` chip (the review
    found inline-block children used to become candidates of their own and
    delete the parent from the scan via the innermost-only rule);
  * glue chain: >=3 prose words fused with ``&nbsp;`` flags; a stat/math
    run (``alpha = 4``) and a middot contact strip stay quiet;
  * contrast: an inherited light ink on a pale highlight span flags; the
    severe defect must survive even when it sits AFTER dozens of borderline
    (3.0 < r < 7.0) runs in DOM order (the review found a fixed 80-sample
    DOM-order cap could evict it); an ``oklch()`` ground is unjudgeable and
    must neither flag nor crash;
  * track void: a vertical header spine stretched by
    ``justify-content: space-between`` flags TRACK/INNER-VOID; a
    height-aligned horizontal header row stays quiet.

Skipped when Playwright/Chromium isn't installed.
"""
from __future__ import annotations

import argparse

import pytest

from _posterly import polish as _polish


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _chromium_available(),
    reason="playwright + chromium not available",
)


def _args(html) -> argparse.Namespace:
    return argparse.Namespace(
        html=str(html), canvas=None, settle_ms=200,
        mathjax_timeout_ms=5000, wide_min_ratio=0.65,
        tall_max_ratio=0.70, tall_min_ratio=0.36, square_min_ratio=0.55,
        max_space_between_fill=0.05, max_card_trailing=0.10,
        max_card_inner_void=_polish.DEFAULT_CARD_INNER_VOID,
        min_card_inner_void_px=_polish.DEFAULT_CARD_INNER_VOID_PX,
        min_contrast=_polish.DEFAULT_MIN_CONTRAST,
        min_unprotected_wraps=_polish.DEFAULT_MIN_UNPROTECTED_WRAPS,
        strict=False,
    )


def _run(tmp_path, capsys, html: str) -> str:
    poster = tmp_path / "poster.html"
    poster.write_text(html, encoding="utf-8")
    rc = _polish.cmd_polish(_args(poster))
    out = "".join(capsys.readouterr())
    assert rc == 0  # all soft under non-strict
    return out


# Minimal chrome polish requires: poster + column + one tagged filled card.
_SHELL = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 24in 18in; margin: 0; }}
  * {{ margin: 0; box-sizing: border-box; }}
  body {{ font-family: Georgia, serif; font-size: 20px; line-height: 1.4; }}
  .card {{ background: #ffffff; padding: 12px; }}
  {css}
</style></head>
<body>
  <div data-measure-role="poster" style="width: 2304px">
  {header}
  <div data-measure-role="column" style="width: 640px">
    <div class="card" data-measure-role="card">
      <p>A normal filled body card paragraph long enough to wrap onto some
         lines and end at a natural full measure without any runt at all,
         with more following words that keep every line comfortably full
         to the right margin of the card box.</p>
    </div>
    {body}
  </div>
  </div>
</body></html>
"""


def test_generic_widow_survives_inline_block_chip(tmp_path, capsys) -> None:
    # .custom-lede is NOT a whitelisted prose class. Its last visual line is
    # a lone stranded word; the early inline-block chip must not delete the
    # parent block from the generic scan.
    css = """
      .custom-lede { width: 400px; }
      .chip { display: inline-block; background: #eeeeee; padding: 2px 6px; }
    """
    body = """
      <div class="custom-lede"><span class="chip">NEW</span>
        Sharpening concentrates probability mass onto the strongest latent
        reasoning paths available alone
      </div>
    """
    out = _run(tmp_path, capsys, _SHELL.format(css=css, header="", body=body))
    assert "WIDOW: <div class='custom-lede'>" in out
    assert "single-stranded-word bar" in out


def test_glue_chain_flags_prose_but_not_stat_or_list_idioms(
        tmp_path, capsys) -> None:
    css = ".card p { width: 460px; }"
    body = """
      <div class="card">
        <p>The method holds output length&nbsp;and&nbsp;keeps&nbsp;improving
           across every training step we measured in the run.</p>
        <p>Setting the exponent (&alpha;&nbsp;=&nbsp;4) sharpens the whole
           distribution toward the strongest latent reasoning paths.</p>
        <p>University&nbsp;&middot;&nbsp;Code&nbsp;&middot;&nbsp;Contact are
           joined as a footer-style separator strip in this line.</p>
      </div>
    """
    out = _run(tmp_path, capsys, _SHELL.format(css=css, header="", body=body))
    assert "GLUE-CHAIN" in out
    assert "length and keeps improving" in out
    # stat/math run and middot strip are exempt idioms
    assert out.count("WARN: GLUE-CHAIN") == 1


def test_contrast_severe_defect_survives_many_borderline_runs(
        tmp_path, capsys) -> None:
    # 301 DISTINCT borderline (~4.2-5:1) class/color combos precede one
    # severe (~1.3:1) mark in DOM order. This exercises BOTH review repros:
    # the old fixed 80-sample DOM-order cap (round 1) and the 300-combo
    # backstop that used to refuse new keys instead of evicting the current
    # worst (round 3). The severe pair must still be reported; borderline
    # combos must not warn at the default 3.0 floor. Inline spans keep the
    # fixture inside the print viewport -- elementsFromPoint only resolves
    # on-canvas points (off-canvas overflow is `measure`'s job).
    per_class = "\n".join(
        f".m{i} {{ color: "
        f"#7{i % 10}7{(i // 10) % 10}7{(i // 100) % 10}; }}"
        for i in range(301)
    )
    css = f"""
      {per_class}
      .padnote {{ background: #0c5b63; color: #ffffff; padding: 8px; }}
      .mark {{ background: #cfe6e4; }}
      .okl {{ background: oklch(0.62 0.1 200); color: #ffffff; }}
      .oklfg {{ color: oklch(0.9 0.02 200); }}
      .pokl {{ position: relative; color: #ffffff; }}
      .pokl::before {{ content: ""; position: absolute; inset: 0;
                       background: oklch(0.95 0.01 200); }}
    """
    borderline = " ".join(
        f'<span class="m{i}">run {i}</span>' for i in range(301)
    )
    body = f"""
      <div class="card">
        <p>{borderline}</p>
        <div class="padnote">Diversity kept: <span class="mark">4.05</span></div>
        <p class="okl">text on an oklch ground is unjudgeable</p>
        <p class="oklfg">a near-white oklch INK on white is unjudgeable too</p>
        <p class="pokl">white text over a pale oklch pseudo fill must skip,
           not read through the pseudo to a white-on-white verdict</p>
      </div>
    """
    out = _run(tmp_path, capsys, _SHELL.format(css=css, header="", body=body))
    assert "CONTRAST: <span class='mark'>" in out
    assert "#cfe6e4" in out
    # borderline ~4.5:1 muted spans stay quiet at the 3.0 floor
    assert "class='m1'" not in out and "class='m77'" not in out
    # oklch ground / oklch foreground / oklch-painted ::before: skipped as
    # unjudgeable -- no crash, no white-on-white nonsense
    assert "class='okl'" not in out
    assert "class='oklfg'" not in out
    assert "class='pokl'" not in out


def test_track_void_flags_spine_not_aligned_row(tmp_path, capsys) -> None:
    css = """
      .spine { display: flex; flex-direction: column;
               justify-content: space-between; height: 1200px;
               width: 300px; background: #f7f7f7; }
      .rowhead { display: flex; align-items: center; gap: 24px;
                 height: 160px; background: #f0f0f0; }
    """
    header = """
      <div class="spine" data-measure-role="header">
        <div>Wordmark block at the very top of the spine track.</div>
        <div>Legend block pushed far down by the space-between rule.</div>
      </div>
      <div class="rowhead" data-measure-role="footer">
        <div>Left title block, height-aligned.</div>
        <div>Right byline block, same row.</div>
      </div>
    """
    out = _run(tmp_path, capsys, _SHELL.format(css=css, header=header, body=""))
    assert "TRACK/INNER-VOID: the header track <spine>" in out
    assert "space-between" in out
    # the height-aligned horizontal footer row must stay quiet
    assert "footer track" not in out


def test_track_void_wrapper_and_positioned_children(tmp_path, capsys) -> None:
    # Review round 2/3 repros, three states on wrapped tracks:
    #   wrapA -- the space-between sits on a lone `.inner` WRAPPER, not the
    #     track itself; the unwrap must still find the void -> flag;
    #   wrapB -- same, but a wide SUBSTANTIVE positioned <figure> child of
    #     the OUTER track covers the band (must survive the unwrap) -> quiet;
    #   wrapC -- same as wrapA but the positioned box is visibility:collapse
    #     WITH an opaque background -- the veto element's own invisibility
    #     must be tested with the full chain, so it must NOT mask -> flag.
    css = """
      .wrapA, .wrapB, .wrapC, .wrapD, .wrapE {
        position: relative; height: 1100px;
        width: 300px; background: #f7f7f7; }
      .inner { display: flex; flex-direction: column;
               justify-content: space-between; height: 100%; }
      .absfig { position: absolute; left: 0; top: 120px; width: 100%;
                height: 860px; background: #dddddd; }
      /* collapse + opaque bg: the veto element's OWN invisibility must be
         tested with the full chain (display/hidden/collapse/opacity) */
      .ghost { position: absolute; left: 0; top: 120px; width: 100%;
               height: 860px; visibility: collapse; background: #dddddd; }
      .abssvg { position: absolute; left: 0; top: 120px; }
      /* fully transparent bg (alpha 0, non-black serialization) must not
         count as a painted fill */
      .hollow { position: absolute; left: 0; top: 120px; width: 100%;
                height: 860px; background: rgba(255, 0, 0, 0); }
      .ghost-ink { opacity: 0; }
      .ghost-svg { visibility: hidden; }
    """
    header = """
      <div class="wrapA" data-measure-role="header">
        <div class="inner">
          <div>Top block of wrapped track A.</div>
          <div>Bottom block of wrapped track A.</div>
        </div>
      </div>
      <div class="wrapB" data-measure-role="header">
        <figure class="absfig"><img src="x.png" alt=""></figure>
        <div class="inner">
          <div>Top block of wrapped track B.</div>
          <div>Bottom block of wrapped track B.</div>
        </div>
      </div>
      <div class="wrapC" data-measure-role="footer">
        <div class="ghost"></div>
        <div class="inner">
          <div>Top block of wrapped track C.</div>
          <div>Bottom block of wrapped track C.</div>
        </div>
      </div>
      <div class="wrapD" data-measure-role="footer">
        <svg class="abssvg" width="300" height="860"><rect width="300"
          height="860" fill="#ccddcc"></rect></svg>
        <div class="inner">
          <div>Top block of wrapped track D.</div>
          <div>Bottom block of wrapped track D.</div>
        </div>
      </div>
      <div class="wrapE" data-measure-role="footer">
        <div class="hollow"><span hidden>hidden filler text</span>
          <span class="ghost-ink">opacity zero filler text</span>
          <svg class="ghost-svg" width="300" height="400"><rect width="300"
            height="400" fill="#ccc"></rect></svg>
        </div>
        <div class="inner">
          <div>Top block of wrapped track E.</div>
          <div>Bottom block of wrapped track E.</div>
        </div>
      </div>
    """
    out = _run(tmp_path, capsys, _SHELL.format(css=css, header=header, body=""))
    assert "TRACK/INNER-VOID: the header track <wrapA>" in out
    assert "<wrapB>" not in out
    assert "TRACK/INNER-VOID: the footer track <wrapC>" in out
    # a bare positioned MEDIA element (the abs <svg> itself) is substantive
    assert "<wrapD>" not in out
    # a positioned container whose only content is INVISIBLE -- hidden text,
    # opacity:0 text, a visibility:hidden svg -- must NOT veto the void
    assert "TRACK/INNER-VOID: the footer track <wrapE>" in out
