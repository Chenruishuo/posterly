# posterly

> Build academic conference posters as a single HTML/CSS file, rendered to print-ready PDF via headless Chromium.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Claude Code skill](https://img.shields.io/badge/Claude_Code-skill-7B2CBF.svg)

**This is a Claude Code skill, not a hosted service.** Clone, install, and either invoke `/posterly` from Claude Code or call the CLIs directly. There is no cloud, no signup, no telemetry.

A poster in `posterly` is **one HTML file** styled for an exact print canvas. The skill ships three neutral templates, four sanity-check CLIs, and a render pipeline that produces a PDF at exact ICML / NeurIPS / ICLR / CVPR / ASP-DAC dimensions. Inside Claude Code, `/posterly` walks you through venue lookup → template pick → content fill → render — see `SKILL.md` for the full workflow Claude Code follows.

---

## Why HTML + CSS, not LaTeX?

- **Tweak loop in seconds, not minutes.** Edit CSS, refresh — vs. LaTeX `recompile + scan log + re-open PDF`.
- **Modern layout primitives.** Flexbox, grid, gradients, `text-wrap: balance`, web-fonts — all things LaTeX poster classes (`tcbposter`, `tikzposter`, `beamerposter`) either don't have or need package-on-package for.
- **Programmatically lintable.** Every "is this column overflowing?" check that you'd do by squinting at a PDF is a Playwright geometry query here.
- **Exact print output.** `@page { size: 60in 36in }` + Chromium's `page.pdf()` produces a PDF whose dimensions are exactly the canvas — not "approximately A0 after scaling".

Trade-off: no native math typesetting; templates load MathJax 3 from a CDN by default. To go offline, download a MathJax v3 release and change the template's `<script src=…>` to `mathjax/es5/tex-svg.js` — there's an inline comment next to the CDN link in each template showing exactly which line to edit.

---

## Install

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
```

All four `poster_check.py` calls should print `PASS` and `render_preview.py` should write `poster_preview.pdf` + `poster_preview.png` into the directory. If that works, install is good.

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
├── examples/hello_world ← end-to-end smoke fixture
└── tests/               ← pytest suite (canvas / preflight / polish / verify-final)
```

The four sanity-check CLIs at a glance:

- `preflight`     — static lint: LaTeX residue, raw `<` inside math, missing local images, remote-image warnings (a print poster should be self-contained), missing `data-measure-role` markup.
- `measure`       — print-emulated geometry: column-bottom spread, gap to footer, poster bbox aligned to the page.
- `polish`        — soft visual checks: figure-AR sizing, typography orphans, space-between fill.
- `verify-final`  — `pdfinfo`-based PDF sanity: page count, dimensions, file size.

Detailed thresholds and tuning flags are in `SKILL.md`. See `templates/README.md` for the template gallery and the conventions a new template must follow.

---

## Customizing your poster

The three knobs you'll actually touch:

- **Colors / fonts**: edit `:root` design tokens (`--accent`, `--gold`, `--font-serif`, …) in the template you copied.
- **Logos**: drop into the same directory as `poster.html`, reference as `images/your_logo.png`.
- **QR code**: templates ship with an inline SVG placeholder so they render offline. Generate a real QR with `qrencode -o qr.png -s 12 "<url>"` (Linux) or `python -c "import qrcode; qrcode.make('<url>').save('qr.png')"`, then change the QR `<img src=…>`.

---

## Development

posterly ships as a clone-only Claude Code skill — `pyproject.toml` carries runtime + dev dependency declarations and pytest config only; nothing is published to PyPI.

```bash
python -m pip install "playwright>=1.40" "pytest>=7"
python -m playwright install chromium
python -m pytest          # or: pytest -q
```

Tests cover canvas parsing (incl. named sizes + `@page` extraction), preflight math-delimiter coverage, line-number preservation, polish role-validation, the `measure` / `polish` nav-timeout fail-fast, and the `verify-final` input gates plus its `pdfinfo` parsing / dimension-and-rotation logic (via a monkeypatched `pdfinfo`, no Poppler needed). The end-to-end `pdfinfo` round-trip on a real PDF is exercised by a Poppler-gated integration test against `examples/hello_world` (skipped when `pdfinfo` is absent or the example PDF hasn't been rendered yet).

---

## License

MIT. See [LICENSE](LICENSE).
