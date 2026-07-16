# ADAPT-IQ Questionnaire & Scoring Rubric (Mathematics 11/12)

**Status.** Designed for this implementation by Claude (Fable 5) in the role
of an educational psychologist: indirect, behaviour-based items that profile
*how* a learner acquires mathematics. **Not clinically validated** — a
heuristic planning instrument, not a diagnostic. Learning-style models are
scientifically contested; modality here is a format *preference* signal only.
The Regular/Specialized mode choice is made explicitly by the user on the
landing page and is **never** inferred from answers.

Machine-readable source of truth: `src/preprocessing/rubric.py`.
`tests/test_rubric_docs_sync.py` keeps this file aligned with the code.

The instrument outputs a learner profile:

| Feature | Values | Derived from |
|---|---|---|
| `learning_method` | memorizer · example_driven · conceptual · visual_learner · practice_driven | B1 + B3 votes (+ visual-tally nudge) |
| `learning_pace` | slow · moderate · fast | mean pace points C1–C4 |
| `break_frequency` | low · medium · high | mean break points C1–C4 |
| `engagement_preference` | visual · auditory · kinesthetic · reading_writing | modality tally B1–B4, C1, C4, D2 |
| `problem_solving_style` | analytical · pattern · procedural · visual · collaborative | B2 votes |
| `cognitive_complexity` | 0–1 | NLP over A1–A3, D1, D2 |
| `foundational_knowledge_score` | 0–100 | A1–A3 rubric |
| `previous_marks` | 0–100 | E1 (median-imputed if blank) |

---

## Section A — Foundational maths understanding (open-ended)

Per question: **0–8 points** keyword coverage (2 per concept group, synonyms
count once) **+ 0–2** sentence-complexity bonus. Overall score = mean × 10.

| ID | Question | Concept groups (2 pts each) |
|----|----------|------------------------------|
| A1 | Explain in your own words what a 'function' means in maths. You may use an example. | input/output/x/value · relation/mapping/rule/machine · unique/exactly one/only one · domain/range/set |
| A2 | Why can we not divide a number by zero? Explain your thinking. | undefined/not defined/meaningless · infinity/larger and larger · multiplication/inverse · no number/nothing times |
| A3 | What does the slope of a straight line tell you? Explain simply, as if to a friend. | steep(ness)/inclination/angle · rate of change/rise/run · gradient · direction/increasing/decreasing |

## Section B — Learning approach & cognitive style

**B1. Your teacher introduces a brand-new formula. What do you naturally do first?**

| Option | Method vote | Modality |
|---|---|---|
| Memorize it so I can use it in the exam | memorizer | — |
| Look at a solved example that uses it | example_driven | — |
| Try to understand where the formula comes from | conceptual | — |
| Draw a picture or graph of what it means | visual_learner | visual +2 |
| Immediately try a practice question with it | practice_driven | kinesthetic +1 |

**B2. When you face a maths problem you have never seen before, what is your usual first move?**

| Option | Style vote | Modality |
|---|---|---|
| Break it into smaller parts | analytical | — |
| Look for a pattern from problems I know | pattern | visual +1 |
| Search for a formula that fits | procedural | reading/writing +1 |
| Draw a diagram or graph of the situation | visual | visual +2 |
| Ask a friend or teacher how to start | collaborative | auditory +1 |

**B3. How do you usually revise before a maths exam?**

| Option | Method vote | Modality |
|---|---|---|
| Re-read my formula list until I know it by heart | memorizer | reading/writing +1 |
| Redo the solved examples from the textbook | example_driven | — |
| Go back to WHY each method works, then practise a little | conceptual | — |
| Make colourful summary sheets, graphs and mind-maps | visual_learner | visual +2 |
| Solve as many new problems as possible against the clock | practice_driven | kinesthetic +1 |

**B4. You need to learn how the graph of y = x² changes when it becomes y = (x-2)² + 3. Which would you pick first?**

| Option | Modality |
|---|---|
| Watch an animation of the graph shifting | visual +2 |
| Have someone talk me through it step by step | auditory +2 |
| Plot the points myself and see what happens | kinesthetic +2 |
| Read a written explanation with the rules | reading/writing +2 |

**Derivations.** `learning_method` = majority of B1+B3 votes (tie → B1's
vote); if the total visual modality tally reaches 6, the label is nudged to
`visual_learner`. `problem_solving_style` = B2 vote.

## Section C — Study habits, attention span & breaks

Pace points 0(slow)–2(fast); break points 0(low)–2(high need).

**C1. Imagine a 40-minute maths topic to study tonight. Which best describes your natural approach?**

| Option | Pace | Break | Modality |
|---|---|---|---|
| Study it continuously without breaks | 2 | 0 | — |
| Take a 5-minute break after 20 minutes | 1 | 1 | — |
| Split the topic over two shorter sessions | 0 | 2 | — |
| Study with a friend and discuss along the way | 1 | 1 | auditory +1 |

**C2. How long can you usually stay on one maths exercise before you feel like switching to something else?**

| Option | Pace | Break |
|---|---|---|
| Less than 10 minutes | 0 | 2 |
| 10–20 minutes | 1 | 2 |
| 20–40 minutes | 1 | 1 |
| More than 40 minutes | 2 | 0 |

**C3. While studying alone, how often do you notice you have drifted off or picked up your phone?**

| Option | Pace | Break |
|---|---|---|
| Very often — every few minutes | 0 | 2 |
| Sometimes | 1 | 1 |
| Rarely — I stay on task | 2 | 0 |

**C4. Your ideal place to study maths is…**

| Option | Pace | Break | Modality |
|---|---|---|---|
| Somewhere quiet where I am alone | 1 | 1 | — |
| With soft music or background sound | 1 | 1 | auditory +1 |
| With friends so we can talk it through | 1 | 1 | auditory +1 |
| Somewhere I can move around or stand | 1 | 2 | kinesthetic +1 |

`learning_pace`: mean pace < 0.7 → slow; > 1.4 → fast; else moderate.
`break_frequency`: mean break < 0.7 → low; > 1.4 → high; else medium.
C2/C3 are the indirect attention-span/self-regulation probes.

## Section D — Self-reflection & metacognition

**D1 (open).** *How do you know you have understood a maths topic well enough?*
Metacognition 0–4 (+1 per group): explain/teach · without help/on my own ·
test myself/practice questions/solve problems/quiz · mistakes/check/compare.
Sentiment on D1 → `reflection_sentiment`.

**D2 (open).** *Describe one time you finally understood a maths idea that had
confused you. What made it click?* Modality keyword hits (+1 each):
visual (video(s), diagram(s), graph, picture, animation, watch, drew,
drawing) · auditory (listen(ing), explained, discussion, talk, told me, said)
· kinesthetic (tried, practice, practising, doing, worked through,
experiment, hands) · reading/writing (notes, read(ing), wrote, writing,
summary, textbook).

**D3. Before a maths test, you usually feel…** → confidence 0–3:
Well prepared and calm (3) · Mostly prepared, a few doubts (2) ·
Unsure what to expect (1) · Anxious even when I have studied (0).

## Section E — Academic performance snapshot

**E1 (numeric, optional).** Your approximate percentage in your last maths
exam (optional). Blank → dataset-median imputation.

**E2. In your last maths exam, where did you lose the most marks?** → gap:
Concepts I never fully understood (conceptual) ·
Silly mistakes in things I knew (accuracy) ·
I ran out of time (speed) ·
Hard application/HOTS questions (application).

---

## Worked example

B1 = "Draw a picture or graph of what it means" (visual_learner, visual +2);
B3 = "Make colourful summary sheets, graphs and mind-maps" (visual_learner,
visual +2) → `learning_method = visual_learner`.
B2 = "Draw a diagram or graph of the situation" → style `visual`, visual +2.
B4 = animation (+2), D2 mentions "video" and "graph" (+2) → visual tally 10 →
`engagement_preference = visual`.
C1 split sessions (0,2) · C2 10–20 min (1,2) · C3 sometimes (1,1) ·
C4 move around (1,2) → pace mean 0.75 → `moderate`; break mean 1.75 → `high`.

The learner-method rules that turn these labels into study strategies live in
`src/rules_engine/engine.py` (`METHOD_RULES`, `PACING_RULES`, `BREAK_RULES`,
`ENGAGEMENT_RULES`, `ASSESSMENT_RULES`, `GAP_ADVICE`); chapter resources come
from `src/curriculum/cbse_math.py` + `src/resources/finder.py`.
