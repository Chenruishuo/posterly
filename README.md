# posterly

> Build academic conference posters as a single HTML/CSS file, rendered to print-ready PDF via headless Chromium.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Claude Code skill](https://img.shields.io/badge/Claude_Code-skill-7B2CBF.svg)

**This is a Claude Code skill, not a hosted service.** Clone, install, and either invoke `/posterly` from Claude Code or call the CLIs directly. There is no cloud, no signup, no telemetry.

> 🚧 **Codex version in the works.** A Codex-compatible port is on the way. If posterly is useful to you, a ⭐ and your suggestions / issues are always welcome!

A poster in `posterly` is **one HTML file** styled for an exact print canvas. The skill ships three neutral templates, four sanity-check CLIs, and a render pipeline that produces a PDF at exact ICML / NeurIPS / ICLR / CVPR dimensions. Inside Claude Code, `/posterly` walks you through venue lookup → template pick → content fill → render — see `SKILL.md` for the full workflow Claude Code follows.

---

## Showcase

Three real conference posters — built with `posterly` from **publicly-available papers** (the authors' own) and shipped here as worked examples. Every one passes `preflight`, `measure`, and `polish`; click a thumbnail for the print-ready PDF, or open the editable source under `examples/`.

*Tooling: each was produced by **Claude Opus 4.7 / 4.8** (reasoning effort `xhigh`) driving `posterly`, with **GPT-5.5** (`xhigh`) as the secondary model for the paper-to-poster content audit.*

<p align="center">
  <a href="docs/showcase/powerflow_icml2026.pdf"><img src="docs/showcase/powerflow_icml2026.jpg" alt="PowerFlow — ICML 2026 poster" width="840"></a><br>
  <b>PowerFlow: Unlocking the Dual Nature of LLMs via Principled Distribution Matching</b><br>
  ICML 2026 · Chen, Chen, Li, Huang (IIIS, Tsinghua) · <a href="https://arxiv.org/abs/2603.18363">arXiv</a> · <a href="https://github.com/Chenruishuo/PowerFlow">code</a> · <a href="examples/powerflow_icml2026/poster.html">source</a> · <a href="docs/showcase/powerflow_icml2026.pdf">PDF</a>
</p>

<p align="center">
  <a href="docs/showcase/tdgfn_icml2026.pdf"><img src="docs/showcase/tdgfn_icml2026.jpg" alt="TD-GFN — ICML 2026 poster" width="840"></a><br>
  <b>Beyond the Proxy: Trajectory-Distilled Guidance for Offline GFlowNet Training (TD-GFN)</b><br>
  ICML 2026 · Chen, Wang, Hu, Li, Huang (IIIS, Tsinghua) · <a href="https://arxiv.org/abs/2505.20110">arXiv</a> · <a href="https://github.com/Chenruishuo/TD-GFN">code</a> · <a href="examples/tdgfn_icml2026/poster.html">source</a> · <a href="docs/showcase/tdgfn_icml2026.pdf">PDF</a>
</p>

<p align="center">
  <a href="docs/showcase/optail_neurips2024.pdf"><img src="docs/showcase/optail_neurips2024.jpg" alt="OPT-AIL — NeurIPS 2024 poster" width="840"></a><br>
  <b>OPT-AIL: Provably &amp; Practically Efficient Adversarial Imitation Learning with General Function Approximation</b><br>
  NeurIPS 2024 · Xu, Zhang, Chen, Sun, Yu (Nanjing University · Polixir.ai) · <a href="https://arxiv.org/abs/2411.00610">arXiv</a> · <a href="https://github.com/LAMDA-RL/OPT-AIL">code</a> · <a href="examples/optail_neurips2024/poster.html">source</a> · <a href="docs/showcase/optail_neurips2024.pdf">PDF</a>
</p>

> A **theory-heavy** paper — loss functions, optimism-regularized Bellman error, eluder coefficients, complexity tables, theorem boxes — all typeset via MathJax and clearing every gate. Drafted end-to-end (paper → print-ready PDF) in **1 h 11 m**.

The ICML posters are four-column landscape; OPT-AIL is three-column. All carry the `data-measure-role` markup the gates read and double as the largest end-to-end fixtures in the repo: copy one, swap in your content, and re-render with `tools/render_preview.py examples/<name>/poster.html`.

---

## Why HTML + CSS, not LaTeX?

- **Tweak loop in seconds, not minutes.** Edit CSS, refresh — vs. LaTeX `recompile + scan log + re-open PDF`.
- **Modern layout primitives.** Flexbox, grid, gradients, `text-wrap: balance`, web-fonts — all things LaTeX poster classes (`tcbposter`, `tikzposter`, `beamerposter`) either don't have or need package-on-package for.
- **Programmatically lintable.** Every "is this column overflowing?" check that you'd do by squinting at a PDF is a Playwright geometry query here.
- **Exact print output.** `@page { size: 60in 36in }` + Chromium's `page.pdf()` produces a PDF whose dimensions are exactly the canvas — not "approximately A0 after scaling".

Trade-off: no native math typesetting; templates load MathJax 3 from a CDN by default. To go offline, download a MathJax v3 release and change the template's `<script src=…>` to `mathjax/es5/tex-svg.js` — there's an inline comment next to the CDN link in each template showing exactly which line to edit.

---

## Install

**The lazy way — hand it to your agent.** Paste this to Claude Code (or any coding agent):

> Install this Claude Code skill for me: https://github.com/Chenruishuo/posterly

It will clone the repo into `~/.claude/skills/`, install the Python deps, and run the smoke test. The manual steps below are the fallback (or for a non-agent setup).

```bash
# 1. Clone into ~/.claude/skills/ for Claude Code auto-discovery
git clone https://github.com/Chenruishuo/posterly ~/.claude/skills/posterly
cd ~/.claude/skills/posterly

# 2. Python deps
python -m pip install "playwright>=1.40"
python -m playwright install chromium
# On a fresh Linux box you may also need the system libs Chromium links against:
#   python -m playwright install --with-deps chromium
#   # or sudo apt install libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
#   #                     libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
#   #                     libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2

# 3. System dep for verify-final's pdfinfo
#    Linux:   apt install poppler-utils
#    macOS:   brew install poppler
#    Windows: choco install poppler

# 4. Smoke test
cd examples/hello_world
python ../../tools/poster_check.py preflight  poster.html
python ../../tools/poster_check.py measure    poster.html
python ../../tools/poster_check.py polish     poster.html
python ../../tools/render_preview.py          poster.html
python ../../tools/poster_check.py verify-final poster_preview.pdf --from-html poster.html

# 5. (dev) run the test suite
python -m pip install "pytest>=7" && python -m pytest
```

All four `poster_check.py` calls should print `PASS` and `render_preview.py` should write `poster_preview.pdf` + `poster_preview.png` into the directory. If that works, install is good.

**Tests (dev):** posterly is clone-only — no PyPI; `pyproject.toml` holds the deps + pytest config. The suite covers the four gates' logic plus Poppler- and Chromium-gated end-to-end checks against `examples/hello_world` (auto-skipped when those binaries aren't present).

---

## What's in here

```
posterly/
├── SKILL.md             ← workflow Claude Code follows when you /posterly
├── tools/
│   ├── poster_check.py  ← preflight / measure / polish / verify-final CLIs
│   ├── render_preview.py← print-emulated PDF + thumbnail PNG
│   └── _posterly/       ← internal modules
├── templates/           ← landscape_4col, landscape_hero, portrait_2col
├── examples/
│   ├── hello_world      ← smallest poster that clears every gate (install check)
│   ├── powerflow_icml2026 ← real ICML 2026 poster (4-col landscape)
│   ├── tdgfn_icml2026     ← real ICML 2026 poster (4-col landscape)
│   └── optail_neurips2024 ← real NeurIPS 2024 poster (3-col, math-heavy)
├── docs/showcase/       ← rendered PDFs + thumbnails for the showcase above
└── tests/               ← pytest suite (canvas / preflight / polish / verify-final)
```

The four sanity-check CLIs at a glance:

- `preflight`     — static lint: LaTeX residue, raw `<` inside math, missing local images, remote-image warnings (a print poster should be self-contained), missing `data-measure-role` markup.
- `measure`       — print-emulated geometry: column-bottom spread, gap to footer, poster bbox aligned to the page.
- `polish`        — soft visual checks: figure-AR sizing, broken/zero-size images (FIG/BROKEN), typography orphans, space-between fill, card trailing whitespace (CARD/TRAILING — a stretched card padded with blank space).
- `verify-final`  — `pdfinfo`-based PDF sanity: page count, dimensions, file size.

Detailed thresholds and tuning flags are in `SKILL.md`. See `templates/README.md` for the template gallery and the conventions a new template must follow.

---

## Customizing your poster

The three knobs you'll actually touch:

- **Colors / fonts**: edit `:root` design tokens (`--accent`, `--gold`, `--font-serif`, …) in the template you copied.
- **Logos**: drop into the same directory as `poster.html`, reference as `images/your_logo.png`.
- **QR code**: give `/posterly` your paper/code URL and Claude generates the QR for you — the showcase posters' codes were made this way. Templates ship an inline SVG placeholder so they render offline; to make one by hand, `qrencode -o qr.png -s 12 "<url>"` (Linux) or `python -c "import qrcode; qrcode.make('<url>').save('qr.png')"`, then point the QR `<img src=…>` at it.

---

## License

MIT. See [LICENSE](LICENSE).
