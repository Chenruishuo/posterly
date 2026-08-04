# Poster copy voice — the de-AI style pass

Design-level fingerprints are handled by anti-convergence (DESIGN-AXES) and the microcopy/emphasis rules (SKILL.md Step 3). This doc handles the **words themselves**: the statistical tells of LLM prose — "AI flavor" — in reader-facing poster copy. Sources: Wikipedia's *Signs of AI writing* (WikiProject AI Cleanup's catalog, built from thousands of flagged articles), the open-source humanizer skill lineage (blader/humanizer, conorbronsdon/avoid-ai-writing), and Chinese 去AI味 practice — **filtered to what applies to academic poster copy**, which is short, telegraphic, and legitimately uses devices those guides ban.

**Scope**: every reader-facing string — banner TL;DR, card prose and bullets, takeaways, captions, section titles, stat labels, microcopy (eyebrows, QR label, footer) — in whichever language the poster is written. English and Chinese tell-lists below.

**When it runs** (wired into SKILL.md):
1. **While drafting (Step 3)** — write copy with these lists in mind; copy born clean needs no sweep.
2. **One dedicated sweep** over all copy after content fill, **before** the Step 4 measure loop — word edits are free before layout tuning and cost a re-tuned layout after (Gate B's timing rule).
3. **Step 6.5 re-scan** — the polish loop writes new sentences ("a key advantage of…"), so the final reviewer re-checks even if the Step 3 sweep was clean.

## The genre carve-out — read before fixing anything

Generic humanizer guides are written for essays and blog posts; several of their rules would *wreck* a poster. These are poster-genre conventions, **not** AI tells — never "fix" them:

- **Telegraphic fragments** in stats, takeaways, and captions (`3.2× faster on A100`). Subjectless is the genre's correct register.
- **`**Term**: description` bullets** inside cards. Banned in blog prose, standard on posters.
- **Earned bold** — governed by SKILL.md's Emphasis discipline (no quota in either direction), not by the "one bold per section" blog rule.
- **Short punchy one-liners** in takeaways — provided each carries a number or a noun, not a vibe.
- **Terms of art, verbatim and repeated**: *robust(ness)*, *attention*, *significant* in its statistical sense, *comprehensive* / *novel* inside a benchmark's or task's proper name, *state-of-the-art* when it is the actual claim and a number backs it. Never synonym-swap a term of art to sound varied — synonym cycling is itself a tell (see below). Chinese equally: 鲁棒性、显著(统计意义)、泛化 are terms, not flavor.

What the pass targets is the **rhetoric**, not the format: decorative evaluation words, formula constructions, manufactured significance.

## Judgment rules (these outrank any word list)

1. **Clusters, not single hits.** One "leverage" doesn't make copy AI-flavored; "leverage" + "seamlessly" + a rule-of-three + an "-ing" tail in one card does. Fix clusters; leave a lone borderline word that reads fine.
2. **The fix is deletion or concretization — never invention.** Replace the evaluation with the number or noun that earned it: "significantly improves accuracy" → "+4.6 pts on MMLU"; "extensive experiments demonstrate" → the experiments' actual headline. If no number exists, the honest fix is deletion, not a different adjective. Facts come only from the paper (Key rule: never invent numbers).
3. **The deletion test.** Cut the suspect phrase; if the sentence loses no information, it was decoration — keep the cut.
4. **Repeat the right word.** Calling the method "our framework", then "the proposed approach", then "this paradigm" is elegant-variation flavor. One name, used every time.
5. **Don't over-sand.** The goal is copy that reads like the paper's authors wrote it at poster scale — not copy that visibly dodged a ban list. A deliberate parallel pair or a single em-dash that helps the line is fine; mechanical avoidance is its own fingerprint.

## English tells

**Decorative vocabulary** (flag when ornamental; technical/named use is exempt): *delve, leverage* (when "use" works)*, harness, seamless(ly), groundbreaking, cutting-edge, pivotal, crucial, testament, underscore/highlight/showcase* (as verbs of self-praise)*, foster, bolster, unleash, elevate, streamline, holistic, tapestry, landscape* (abstract)*, paradigm shift, game-changer, meticulous, intricate, myriad, plethora, vibrant, remarkable, elegant/powerful/novel* (as self-praise)*, significant(ly)* with no number attached.

**Formula constructions**:
- **Negative parallelism**: "not just X, but Y", "It's not X — it's Y", tailing negation chains ("No heuristics. No tuning. Just results."). State the positive claim once.
- **Rule of three**: triplet adjectives or clauses stamped across cards ("fast, scalable, and accurate"). Use the two that matter, or four if four are real.
- **Copula avoidance**: *serves as / stands as / boasts / features* where *is / has* is meant.
- **"-ing" pseudo-analysis tails**: "…, demonstrating the effectiveness of our approach", "…, highlighting the importance of X". Cut the tail or state the concrete finding it gestures at.
- **False ranges**: "from low-level perception to high-level reasoning" when the two aren't endpoints of a real scale — name the actual tasks.
- **Vague attribution**: "recent studies show" with no citation on a poster that cites elsewhere.
- **Hedge stacks**: "could potentially", "may possibly enable". One hedge, or a claim.
- **Emphasis stacking**: *Notably / Importantly / Interestingly* more than about once per poster — the layout already does the emphasizing.
- **Generic closers**: "paves the way for", "opens new avenues", "an important step toward". End the last card on the concrete next thing or on the result itself.
- **Aphorism formulas**: "X is the Y of Z" ("attention is the currency of…"). Replace with the concrete claim.
- **Abstract-opener TL;DR**: a banner that begins "In this work, we propose…" is a paper abstract pasted at 2 m scale. The banner states the claim directly: what it does, what it wins, by how much.
- **Em-dash note**: a weak tell on its own (skilled humans use them); on a poster's short prose, more than one per block reads as interruption — restructure instead.

**Poster-specific hot spots**: figure captions ("illustrating the superiority of our method" → what the figure shows plus the readable conclusion: "Ours stays flat as N grows; baselines blow up past 10⁴"); takeaway slots filled with vibes ("Powerful & general") instead of content; the last card ending on a generic future-work blessing.

## 中文海报的 AI 味

**套话开场与收尾**(海报上直接删,让结论自己站着):综上所述、总而言之、值得注意的是、不难发现、由此可见、"随着…的快速发展"、"在…的时代/背景下"、"近年来,…受到广泛关注"(裸用)、"本文/本工作旨在提出…"(海报不需要论文腔的自我引介——直接说方法做什么)。

**空洞强调词**(无数字跟随时全部可疑):至关重要、不可或缺、举足轻重、里程碑、新范式、革命性、颠覆性、"极大地/大幅"(后面没有数字)、"有效"(裸用)、赋能、彰显、凸显、助力、深入探讨、深度融合、"强大而通用"。修复同英文:数字或名词顶上("大幅提升"→"+4.6 pts"),没有数字就删。

**句式指纹**:
- "不仅…更/而且…"、"并非…而是…" —— 中文版 negative parallelism,正面说一遍就够。
- "首先…其次…最后" —— 海报的卡片结构已经在分段,不需要口头报幕。
- **三连排比与全员对仗**:动宾三连("提升了效率,降低了成本,增强了鲁棒性")、四字词堆砌。一处工整的对仗是修辞;每张卡的标题都是齐整四字对仗是模板腔。
- **"通过…,实现了…,为…奠定了基础"链** —— 一句话背三个空洞动词,拆开只留有数字的那截。

**中文豁免**:学术术语照用不避(鲁棒性、显著性/统计显著、泛化、消融);海报标签体(名词短语卡标题、"数据集:"式列表)是体裁惯例不是 AI 味。

## Running the sweep

After content fill (before the Step 4 loop): read every text node once, top-left to bottom-right, against the two lists — marking clusters, not scattered single hits. Fix each cluster by deletion or concretization per the judgment rules; re-read the fixed block once for meaning drift. After `measure` is green, any further copy fix must hold the block's line count (swap words, don't add them — SKILL.md Gate B's timing rule). The Step 6.5 reviewer item re-scans the polished copy; SKILL.md carries the reviewer prompt.

This pass is judgment, not a script gate — a wordlist checker would false-positive on terms of art (*robust*, *significant*, 显著) exactly where posters use them most, so no tool enforces it; the reviewer and you do.
