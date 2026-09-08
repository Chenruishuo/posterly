---
name: posterly
disable-model-invocation: true
description: "Create or revise academic conference posters in HTML/CSS and export print-ready PDFs. Use for poster design, layout edits, and print export."
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, AskUserQuestion, WebFetch, WebSearch
---


# posterly — HTML/CSS Academic Poster Workflow

A poster is **one HTML file** styled for an exact print canvas, rendered to PDF via Playwright + Chromium. Iterate by **measuring**, not eyeballing — the screen preview lies; only `emulate_media("print")` at the correct viewport tells the truth.

## Mental model

```
   HTML (with @page { size: W H })
     │
     ▼  print-emulate Chromium at W×96 × H×96 px viewport
     │
     ▼  data-measure-role tags identify columns/hero/footer-strip
     │
     ├──→ tools/poster_check.py measure  (HARD GATE — spread < 5 px,
     │                                    gap-to-strip ∈ [30,50] px,
     │                                    intercard gap ∈ [12,50] px,
     │                                    poster bbox aligns to page
     │                                    within ±2 px)
     ├──→ tools/poster_check.py preflight  (LaTeX residue, math `<`, missing imgs)
     ├──→ tools/render_preview.py  (PDF + thumbnail)
     └──→ tools/poster_check.py verify-final  (PDF page count / dims / size)
```

The skill is venue- and lab-neutral by default. Compose a design direction from `templates/DESIGN-AXES.md` (Step 2.5), scaffold from the nearest template in `templates/README.md`, edit `:root` design tokens to match the locked direction, fill TODO placeholders with your paper's content.

## Canvas constants

| Constant | Value | Notes |
|---|---|---|
| `--u` (CSS unit) | print = `1mm`, screen = `1.6px` | Use `calc(N * var(--u))` for ALL sizing. |
| Print viewport (px) | `W_in × 96` × `H_in × 96` | Computed by `poster_check`/`render_preview`. |
| Body cols | 2 / 3 / 4, or 1 hero + 1 column | Per template. |
| Strict alignment | **spread < 5 px** (aim < 3) | Hard, non-negotiable gate. |

<a id="python-environment"></a>

## Python environment

**Invoke Python by the full path of a dedicated, non-base environment.** `/absolute/path/to/dedicated-env/bin/python` is a placeholder: replace it with the verified absolute interpreter path of the current machine's dedicated non-base environment for Posterly tools and Python snippets. Install missing Python dependencies with `/absolute/path/to/dedicated-env/bin/python -m pip install ...`, and run Playwright installation with the same interpreter's `-m playwright`. Never use bare `python`, `python3`, or `pip`, rely on `conda activate`, or install into base. A missing module must be resolved in the dedicated environment, not by falling back to base.

Tool help, diagnostics, and exported examples may use portable shorthand; before executing those commands, expand it to that full path. `run_gates.py` already launches its Python children through `sys.executable`, preserving the selected interpreter. Keep all existing command arguments, installation approval boundaries, and validation obligations.

## Reading contract and execution boundaries

**Before performing each stage, you must read and execute its linked applicable sections**, including substeps, exceptions, examples, manual checks, and prerequisites. Read the required sections, not every referenced file in full. Mandatory instructions and checks remain mandatory; optional helpers remain optional. The routes below do not replace those instructions.

**Paths:** Markdown links are relative to the containing file. Command and inline paths such as `tools/`, `templates/`, `assets/`, `specimens/`, `README`, and `<skill>` are relative to the skill root (the directory containing `SKILL.md`); poster working paths retain their working-directory meaning.

<a id="task-modes"></a>

**Choose the task path before starting.**

- **New poster or overall redesign:** follow the complete design workflow below, including Step 2.5's 2–3 rendered candidates and design lock. Reuse supplied answers under the confirmation policy.
- **Local edit to an existing poster:** when the requested text, number, or asset changes preserve the canvas size/orientation and the accepted design direction, edit the existing working HTML directly. Reuse its current design, tokens, and recorded decisions; **do not recompose or render 2–3 design candidates, ask for another design selection, or copy a fresh gallery scaffold over the poster**. Read the relevant Step 3 authoring/component contracts and writing guidance for the edit, and Step 2 requirements for affected assets. Routine reflow/spacing repairs within the same direction remain local edits and still follow the existing style/fix rules.

Both paths retain source/venue verification, Step 3 authoring/copy/theorem obligations, the mandatory Step 3.5 content audit on the filled or updated poster, Step 4–6 checks and visual inspection, and Step 7 final-file verification/export. Existing unchanged-version preflight/polish reuse remains available; changing text, numbers, assets, or layout invalidates the corresponding old results. Step 6.5 cross-model final review remains strongly recommended. The local-edit path changes design preparation, not those quality requirements.

If the requested work requires a different canvas or design direction, follow the existing confirmation policy before applying the change and use the complete design workflow. Follow the confirmation, non-interactive, identity, system-extension, and upstream-feedback rules in the linked stages.

<a id="confirmation-policy"></a>

**Reuse supplied answers and existing confirmations.** For the same poster and unchanged decision, directly use information the user has already supplied or confirmed in the conversation or project notes: dimensions/orientation, palette, logos, QR target, density/block count, source paths, and content preferences. Explicit “none”, “no preference”, and “you choose” are answers within their stated scope, not missing information. Ask only about missing items or unresolved conflicts; do not repeat a question merely because another workflow stage mentions it. Record answers and keep required source/venue checks: reusing an answer does not waive verification. Do not transfer a choice from a different poster without evidence that it applies here.

**Changes to locked choices still need confirmation.** Before applying a proposed change to the locked canvas size/orientation or design direction, obtain confirmation for that change; an explicit user instruction authorizing that exact change already supplies it and must not be asked again. The existing non-interactive design-direction exception remains as documented. Reusing one preference does not authorize a different system extension, crop/waiver decision, or external action; retain those original approval boundaries and any approval already granted for the same action.

Read the universal [pitfalls](references/pitfalls.md#universal-pitfalls) before authoring; read layout-specific pitfalls and all applicable [visual rules](references/visual-polish.md) before authoring/inspecting affected content. These contain preventive and manual obligations even when automated checks pass. During a fix, consult the relevant rule rather than reloading unrelated cases.

**Style rules 4 and 5 are opt-in requirements.** Enforce the two-hue-family limit (rule 4) and gradient restrictions (rule 5) only when the respective rule is explicitly enabled for the current poster. Otherwise **ignore the corresponding requirements**, including rules repeated as component anti-patterns or recommended catalog conventions; do not reduce palette breadth or remove gradients to satisfy a disabled rule. Other requirements remain in force. Keep tool flags consistent with that choice; see the [style-rule switch contract](references/validation.md#style-gate).

### Step 0 / Step 0.5 / Step 1 — Venue, discovery, and source content

At each stage, read and follow [venue](references/design-workflow.md#venue), [discovery](references/design-workflow.md#discovery), and [content](references/design-workflow.md#content). Apply the [confirmation policy](#confirmation-policy) to missing or conflicting inputs; verify sources even when answers are already supplied.

For palette work, read [palette derivation](templates/THEMES.md#palette-derivation), including seed-independent rules when the user supplies colors and the theme mechanisms in that file.

### Step 2 — Image preprocessing

Read and follow [image preprocessing](references/assets.md#image-preprocessing) for the figures, QR codes, and logos used. Read [Gate A](references/visual-polish.md#gate-a) before figure placement and [Gate E](references/visual-polish.md#gate-e) before logo placement.

Read and execute the [real-figure provenance contract](references/assets.md#figure-provenance) only when adopting it. Otherwise asset verification is `NOT_RUN`, not verified; ordinary image-processing and fidelity requirements still apply.

### Step 2.5 — Compose, show, and lock the design (new posters / redesigns)

For new posters or redesigns, read and follow [design direction](references/design-workflow.md#direction) and [DESIGN-AXES](templates/DESIGN-AXES.md): compose and render 2–3 candidates, then lock the selection. Apply the documented batch and non-interactive rules. [Local edits](#task-modes) keep the accepted direction.

Before preparing fonts or tokens, read direction item 4. Always write `design_tokens.json` at design lock and pass it on every gate run.

### Step 3 — Scaffold, content, and identity

For new scaffolds, read and follow [scaffolding](references/design-workflow.md#scaffold), [template contracts](references/design-workflow.md#templates), and [gallery](templates/README.md). Local edits apply the [Step 3 authoring contracts](references/design-workflow.md#scaffold) to the existing HTML without copying a fresh scaffold. Both paths must follow [identity](references/design-workflow.md#identity) and the [COMPONENTS](templates/COMPONENTS.md) entries for every component used.

Before scaffolding, read the [style gate](references/validation.md#style-gate); run it right after the scaffold and on every layout change within its documented scope.

Read and follow [WRITING](templates/WRITING.md), perform its pre-loop sweep and Step 3's theorem/equation check. Do not try to make an unfilled scaffold pass filled-poster gates.

### Step 3.5 — Content audit

After filling or updating the poster, and before Step 4, read and execute the mandatory [content audit](references/review.md#content-audit) and applicable [review checkpoints](references/review.md#review-checkpoints). Proceed only after every finding is fixed or explicitly recorded as a user-acknowledged tradeoff.

### Step 4 — Budgeted layout loop

Before the first loop, read and follow [measurement](references/validation.md#measure-loop), [enhanced gates](references/validation.md#enhanced-gates), [runner](references/validation.md#gate-runner), [style gate](references/validation.md#style-gate), and [fix discipline](references/validation.md#fix-discipline).

Use the complete `run_gates.py` sequence after each layout change under the documented template/fallback scope. Apply [unchanged-version result reuse](references/validation.md#result-reuse) only when its conditions hold. Follow the hard thresholds and exit-3 circuit breaker; do not reset the budget just to continue grinding or bypass system-extension approval. Consult [tool contracts](references/validation.md#tools) for the commands used.

### Step 5 / Step 6 — Render, inspect, and polish

Read and execute [visual inspection](references/validation.md#visual-inspection), [polish](references/validation.md#polish-workflow), and every applicable [Gate A–G](references/visual-polish.md). Full standalone-polish coverage is required, with reuse only under the [unchanged-version rule](references/validation.md#result-reuse). Fix or explicitly accept each soft warning; hard gates remain mandatory. A green measurement does not replace visual inspection.

### Step 6.5 — Final review (cross-model strongly recommended)

Final review is **strongly recommended**, preferably with a fresh reviewer from a different model family; it is not a delivery prerequisite. When performing it, read and execute [final review](references/review.md#final-review), [cross-model review](references/review.md#cross-model-review), and applicable [checkpoints](references/review.md#review-checkpoints), including evidence, finding resolution, and revalidation after fixes. Use the documented alternatives when cross-model review is unavailable.

### Step 7 — Verification and handover

Read and execute [final verification, exports, bundling, and reporting](references/validation.md#final-verification), including its upstream-feedback consent boundary.

Completion requires the Step 3.5 audit, all applicable hard gates, manual inspections, warning disposition, and Step 7 verification and deliverables. If final review is performed, resolve its findings and revalidate resulting fixes as required.

<a id="section-map"></a>

## Complete section map (including legacy Step / § references)

Use this map for a global overview and legacy Step/Gate/section names; individual instructions link directly to their target sections. Sections were relocated from the original SKILL.md and include approved revisions. `preserved-source` comments identify historical source locations, not byte-for-byte equivalence. Style-rule 4/5 wording throughout follows the opt-in contract above. Any other unresolved pre-existing tensions remain **待确认** for a later content change; that label itself does not waive a rule.

| Original section / lookup term | Current home |
|---|---|
| Step 0; Step 0.5; Step 1 | [Venue](references/design-workflow.md#venue), [discovery](references/design-workflow.md#discovery), [content](references/design-workflow.md#content) |
| Palette derivation | [THEMES: original derivation](templates/THEMES.md#palette-derivation) |
| Step 2; image preprocessing; crop hygiene | [Assets](references/assets.md#image-preprocessing) |
| Step 2.5; DESIGN DIRECTION; fonts/tokens; anti-convergence | [Design direction](references/design-workflow.md#direction) |
| Step 3; BASE DEFENSES; microcopy; emphasis; theorem/equation sanity | [Scaffold](references/design-workflow.md#scaffold) |
| Step 3.5; evidence pack; reviewer prompt | [Content audit](references/review.md#content-audit) |
| Identity mark; anonymous submission | [Identity](references/design-workflow.md#identity) |
| Step 4; fine-tuning; budget; safety nets; preflight | [Measure loop](references/validation.md#measure-loop) |
| Step 5; crop inspection; DPI; identity paint | [Visual inspection](references/validation.md#visual-inspection) |
| Step 6; soft gate; text-wrap | [Polish workflow](references/validation.md#polish-workflow) |
| Step 6.5 | [Final review](references/review.md#final-review) and [cross-model review recommendation](references/review.md#cross-model-review) |
| Step 7; PNG; bundle; upstream feedback | [Final verification](references/validation.md#final-verification) |
| Visual polish gates; Gate A; BANNER/IMAGE-SLOT | [Visual rules](references/visual-polish.md#visual-gates), [Gate A](references/visual-polish.md#gate-a), [banner scaffold rules](references/design-workflow.md#scaffold) |
| Gate B; WIDOW; ORPHAN; GLUE-CHAIN; timing rule | [Typography](references/visual-polish.md#gate-b) |
| Gate C; CARD/TRAILING; CARD/INNER-VOID; CARD/TRACK-MISALIGN; TRACK/INNER-VOID; Fill means substance | [Balance rules](references/visual-polish.md#gate-c) |
| Gate D; LAYOUT/FLEX-BR | [Flex breaks](references/visual-polish.md#gate-d) |
| Gate E; Header logos; title squeeze; rails | [Header rules](references/visual-polish.md#gate-e) |
| Gate G; CONTRAST; optional packing advisor | [Composed contrast and advisor note](references/visual-polish.md#gate-g) |
| Universal / Layout-shared pitfalls | [Universal](references/pitfalls.md#universal-pitfalls), [layout-shared](references/pitfalls.md#layout-pitfalls) |
| When to call an external LLM reviewer | [Three checkpoints](references/review.md#review-checkpoints) |
| Tools; pack; fit-logos; bundled MathJax | [Tool contracts](references/validation.md#tools) |
| Enhanced gates; One-shot gate runner; Style HARD gate | [Enhanced](references/validation.md#enhanced-gates), [runner](references/validation.md#gate-runner), [style](references/validation.md#style-gate) |
| Real-figure provenance gate | [Asset contract](references/assets.md#figure-provenance) |
| Fix discipline; escape hatch; round caps | [Fix discipline](references/validation.md#fix-discipline) |
| Cross-model final review | [Cross-model review recommendation](references/review.md#cross-model-review) |
| Templates; adding a template | [Template rules](references/design-workflow.md#templates) |

<a id="key-rules"></a>

<!-- preserved-source: SKILL.md lines 747-754 -->
## Key rules

- **Never invent paper numbers.** Read the `.tex` source. Bench numbers, datasets, model names — all verifiable.
- **Context discipline in the measure loop.** Never emit the whole poster.html through your output (scaffold via `cp`, edit surgically); don't re-`Read` the full file each iteration — work from `measure`'s edit-targets block (source line + anchor, then read just the surrounding block to confirm before editing). Full re-reads are for: an unfamiliar template, a cross-column re-pack, structural failures, a missing/ambiguous anchor, and the final audit.
- **Respect the circuit breaker.** `measure` exit 3 means the loop is not converging — re-pack / rescope / escalate; don't `--reset-budget` to keep grinding.
- **Card-shadow visibility is non-negotiable.** A poster looks cheap when shadows are clipped.
- **Strict alignment is non-negotiable.** Spread < 5 px or it's not done — do not report success until `measure` exits 0.
- **Preserve user-judgment decisions across sessions.** "Do not revert" notes (`✉ stays on Author X`, `α-sensitivity card removed`) — re-read the user's prior messages before "improving" a section.
<!-- end-preserved-source: 747-754 -->
