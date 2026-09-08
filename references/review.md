# Content and final review instructions

Read [review checkpoints](#review-checkpoints) and [Step 3.5](#content-audit) before the draft content audit, including the full evidence pack and reviewer prompt. The theorem/equation checkpoint remains in [Step 3](design-workflow.md#scaffold). Before final review, read **both** [Step 6.5](#final-review) and [cross-model final review](#cross-model-review); final review is strongly recommended, preferably cross-model, and is not a hard delivery gate. When a review is performed, its evidence, scope, finding-resolution, and revalidation requirements still apply.

Related: [WRITING](../templates/WRITING.md), [Gate B copy-fix timing](visual-polish.md#gate-b), [design lock](design-workflow.md#direction), [validation and rerun discipline](validation.md).

**Review policy:** Step 3.5 content audit remains mandatory. Step 6.5 final review is **strongly recommended**, preferably using a fresh reviewer from a different model family. If cross-model review is unavailable, an external reviewer, fresh subagent, or self-audit may be used instead; absence of cross-model or final review alone does not block delivery. The mandatory draft audit, hard gates, visual inspection, and final file verification are unchanged.

[Shared reading and path rules](../SKILL.md#reading-contract-and-execution-boundaries) apply.

<a id="content-audit"></a>

<!-- preserved-source: SKILL.md lines 144-177 -->
### Step 3.5 — Content audit (mandatory; external reviewer recommended)

**When to run it:** this audits a *filled draft*, so do it once you've scaffolded (Step 3) and put real content into `poster.html` — but **before** you sink renders into the Step 4 measure/balance loop. It sits here, after the filled draft and before the layout loop, because fidelity is a *content* concern, not a layout one: catching a wrong number now costs nothing, catching it after the layout loop wastes every render in between. Repeating the same audit on the *final* poster at Step 6.5 is strongly recommended.

The draft must be audited for paper-to-poster fidelity. Past sessions caught real bugs ONLY here — paper said "20× fewer" but the table gave 16×, "fewest trajectories" was an overclaim vs the actual baselines, theorem preconditions were silently dropped. Skip this and you will discover errors only when standing next to the printed poster.

**How to run it (in order of preference):**

1. **External LLM reviewer with file access (best).** If you have Codex MCP, another Claude session, or any external reviewer that can `Read` paper source files, use that. Select a currently available model that meets the applicable reviewer capability requirements and a high reasoning setting supported by that model and review tool. For example, where supported: `model="gpt-6-astra"`, `model_reasoning_effort="high"`. This is an example, not a fixed model requirement; retain the fresh-context, model-capability, and cross-model conditions for the chosen review mode. Send the evidence pack + reviewer prompt below.

2. **Fresh subagent (second best).** No external reviewer? Spawn one that can `Read` the paper source and give it the same evidence pack + prompt (Claude Code: `Agent` with an explicit `model`; Codex: `spawn_agent`). Two conditions, or it's worthless: **fresh context** (not a fork of yourself — a fork re-runs your blind spots) and a model **no weaker than the one drafting the poster** (pass it explicitly; a cheaper auditor mostly agrees with what it's shown). Fresh eyes, not cross-model independence — this remains a fallback for Step 6.5, whose preferred mode is cross-model review.

3. **Self-audit (last resort).** Walk every numeric claim on the poster and find its `file:line` in the paper source. Build the claim → evidence table by hand. Slower, easier to miss things, but better than skipping.

**Review permissions (all reviewer modes):** Default to read-only access and the minimum permissions needed to inspect evidence; reviewers report findings without editing files. Distinguish sandbox initialization failures from permission denials. For an initialization failure, report the error and use an alternative execution mode supported and authorized by the current environment. Where applicable, follow `codex-call`'s sandbox-init fallback, including `danger-full-access` only when the current environment permits and authorizes that mode; disclose the switch and keep the review read-only. Follow the environment's approval process for any required permission change. Neither a skill instruction nor an initialization error overrides a runtime restriction or permission denial. If no permitted alternative is available, report the unavailable files/tools/operations and incomplete checks, and use the documented reviewer alternatives where feasible. Never claim inaccessible evidence was reviewed.

**Evidence pack the reviewer needs:**
1. The current `poster.html` (full)
2. Paper source path(s) so the reviewer can `Read` the `.tex` and any `results/` CSVs
3. For every numeric claim, the paper `file:line` where the number originates
4. For every theorem/claim, the paper statement verbatim with all preconditions

**Reviewer prompt template** (use this verbatim, fill bracketed parts):

```
Audit the academic-poster draft at [poster.html abs path] against the paper at [main.tex abs path] (and any results in [results dir]). For every number, claim, theorem, dataset name, method-comparison, AND the author block (author order, affiliations, corresponding-author marker vs \icmlcorrespondingauthor / \thanks, grant number) on the poster, produce a claim → evidence table:

  | claim on poster | paper file:line | paper says (verbatim) | match? |

Mark "match?" as: OK / NUMERIC-MISMATCH / OVERCLAIM / MISSING-PRECONDITION / NOT-IN-PAPER / SCOPE-NARROWED.

Then list every NON-OK row as a problem to fix before printing. Be skeptical — "all <method> methods" claims, "best by Nx" claims, and theorem statements without their epsilon/regularity preconditions are the most common silent errors.
```

You may proceed to Step 4 **only after every finding is either fixed or explicitly recorded as "user-acknowledged tradeoff"**. Do not silently defer.

<!-- end-preserved-source: 144-177 -->

<a id="final-review"></a>

<!-- preserved-source: SKILL.md lines 389-397 -->
**Step 6.5 — Final review (strongly recommended; cross-model preferred)**: once `run_gates.py` is all-green and polish warnings are zero-or-waived, a fresh cross-model review is strongly recommended. When performing final review, send the rendered PDF (or its high-res PNG slices) AND the HTML, preferably to a reviewer from a different model family. If that mode is unavailable, the Step 3.5 alternatives remain available (external LLM if available, fresh subagent next, self-audit last). Same evidence-pack rule. The reviewer prompt focuses on five things distinct from Step 3.5:
1. **Visual rhetoric**: does the poster's narrative carry? Are the headline numbers prominent? Is the framework banner readable from 2 m?
2. **Residue**: any `\ref{`, `\cite{`, leftover `TODO`, raw `<` in math, missing image, broken QR link.
3. **Final claim audit**: re-check numbers and overclaims AFTER content has been polished — polish often introduces new claims ("a key advantage of…") that were not in the original draft.
4. **Design coherence** (judgment questions, not a restyle mandate — include the poster's `DESIGN DIRECTION` comment block in the evidence pack): Does the rendered sheet deliver its own concept statement, or do some elements read as pasted in from a different poster? Is the locked hero moment actually where the eye lands first, and is it the only loud element? Do figures sit mounted in the design — each component's *native* mount (ground / keyline / caption where the component has them) consistent with the direction — rather than dropped on top of it? Two component contracts the reviewer must not "fix": the hero-panel img is frameless by design (its stage frames it), and a banner figure is usually captionless. And do the small words and the bolding speak *this* poster's voice — or the scaffold's ("Framework" / "Takeaways" verbatim) and a formula's (the same words bolded on every card, one stock closer stamped throughout)? On emphasis there is no quota in either direction — zero-bold and several-bold cards are both legitimate; the question is only whether each bold earns its place. A miss here is almost always a small fix — retune a token, quiet one competing element, re-mount one figure — never grounds for a redesign. The locked direction and the venue's legibility floors outrank the reviewer's taste: in particular, discard generic "make it bolder" advice (bigger display type, louder colors, added ornament) that isn't answering one of these questions.
5. **AI-flavor scan** (`templates/WRITING.md`): flag *clusters* of AI-writing tells in the final copy — decorative significance words, negative parallelisms, "-ing" pseudo-analysis tails, generic closers; 套话、空洞强调词、三连排比 on a Chinese poster — per that guide's tell-lists AND its genre carve-out (fragments, `**Term**:` bullets, earned bold, and repeated terms of art are poster conventions — do not flag them). The polish loop writes new sentences, so this scan runs even when the Step 3 sweep was clean. Fixes follow the guide's judgment rules (delete or concretize, never invent), and — since `measure` is green by now — must hold each block's line count (Gate B's timing rule).

If final review is performed, fix every finding before declaring the poster done.

<!-- end-preserved-source: 389-397 -->

<a id="review-checkpoints"></a>

<!-- preserved-source: SKILL.md lines 638-647 -->
## When to call an external LLM reviewer (three checkpoints)

The skill works fine without an *external* reviewer — a subagent or self audit is the mandatory floor (Step 3.5) — but a second pair of eyes reliably catches paper-to-poster fidelity bugs you'd otherwise find next to the print station. Three checkpoints, each documented at its home:

1. **Content critique** — Step 3.5 (claim → evidence audit; the canonical reviewer settings *and* the prompt template live there).
2. **Theorem & equation pass** — the quick check right after Step 3 (preconditions survived the scaffold; equations actually render).
3. **Final polish** — Step 6.5, a **strongly recommended cross-model review**, performed after `run_gates.py` is all-green (see [**Cross-model final review**](#cross-model-review)). It is not a hard delivery gate.

The bias is **send when uncertain** — cost 2-3 min, against a silent error in a poster you'll print and stand next to for two hours.

<!-- end-preserved-source: 638-647 -->

<a id="cross-model-review"></a>

<!-- preserved-source: SKILL.md lines 734-737 -->
### Cross-model final review (strongly recommended for Step 6.5)

For Step 6.5, cross-model review is **strongly recommended**, not a hard delivery gate. When using this mode, after `run_gates.py` is all-green and polish warnings are zero-or-waived, open a **fresh, cross-model** thread (a different model family than drafted the poster; use the model-selection guidance in Step 3.5 — e.g. `gpt-6-astra` with `high` when available and from a different family than the drafting model) on the *final artifacts only* — `poster.html`, the rendered PDF/PNG, the paper source, and `GATE_REPORT.json` — passed as **paths, no executor framing**. It re-checks fidelity/overclaims on the *polished* text (polish introduces new claims), residue (`\ref{`, `TODO`, raw `<` in math, missing images, remote URLs), visual rhetoric (headline numbers prominent, banner readable at 2 m), copy voice (AI-flavor clusters per `templates/WRITING.md`, respecting its genre carve-out), design coherence (the sheet delivers its own `DESIGN DIRECTION` block — concept, single hero moment, component-native figure mounts, poster-voiced microcopy and earned emphasis; Step 6.5 item 4's restraint applies), and gate-log coherence. The reviewer *recommends*; it does not edit. Any fix loops back through Step 4/6 — never straight to re-review.

<!-- end-preserved-source: 734-737 -->

