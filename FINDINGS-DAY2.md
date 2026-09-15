# CausalTwin — Day 2 Findings

**Shiv Bisht** | 15 September 2026 | Surface: Microsoft Copilot App

---

Day 1 built a calibrated twin and said the cross-offer effects in it were assumptions,
not findings. Day 2 went to measure them.

They are not there. This is the write-up of a premise that did not survive contact
with its own data, and of the lever that turned up instead.

## 1. The effect this project was built on reaches 1 user in 13,000

The proposal rests on one idea: showing offer A changes how a user reacts to offer B.
For that to happen, A and B have to land near each other.

Counted across 200,000 simulated users over 30 days, with **every** upsell live
including the two that have not shipped:

| | share of users |
|---|---|
| ever see two different contextual upsells | 0.150% |
| see two of them **within 24 hours** | **0.007%** |

Against 54.1M monthly actives that is roughly **3,800 users a month** who are even
eligible for the effect. Optimising every one of them perfectly would move a few
hundred licence requests against a measured 310,000.

The triggers fire on different days, from different behaviour, to mostly different
people. They do not queue up behind each other.

## 2. Every cross-offer effect we assumed measured as exactly zero

Switching each upsell off and replaying the same users, the effect on every other
upsell's click rate, across all twelve contextual pairs, was **0.00 percentage
points.** Not small. Zero, to the precision the samples allow.

The largest assumed effect in the model was -1.10 log-odds between the two image
triggers — the pair Day 1 called "the pair most worth checking against real data."

Measured: **-0.03pp**, which is noise.

Two caveats keep this honest. The daily image limit produced 71 impressions in the
live scenario and 19 in the launch scenario; the file limit produced 34. At those
counts "no effect" and "no data" are the same picture. And the reason the counts are
so small is the reason in section 1 — so both readings lead to the same place.

## 3. The one real interaction is not a sequence

Switching off the persistent CTA improves every contextual upsell at once:

| trigger | CTR with CTA | CTR without | change |
|---|---|---|---|
| image capacity | 14.71% | 21.76% | **+7.06pp** |
| artifact limit | 10.00% | 14.78% | **+4.78pp** |
| file limit | 8.82% | 17.65% | **+8.82pp** |

So interference is real on this surface. It just has nothing to do with what order we
show things in.

One upsell shown every day to 100% of users does more damage than every offer-pair
interaction combined, by a factor of thousands. That is not a sequencing problem and
no sequencing policy addresses it. It is a question of how much constant commercial
pressure the surface carries.

## 4. No sequencing policy can win, and here is the arithmetic

Removing the CTA entirely — the strongest intervention available — decomposes into:

| | contextual upsells gain | CTA's own sales lost | net |
|---|---|---|---|
| today, 3 upsells | +0.48 | -5.00 | **-4.52** |
| after launch, 5 upsells | +2.10 | -5.50 | **-3.40** |

**+0.48 is the entire prize** on today's surface, and collecting it costs 5.00. Ten to
one against. Any softer policy takes a slice of the upside at the same exchange rate,
which is why resting the CTA for 24, 48 and 168 hours all landed within 0.04 of doing
nothing, and why Day 1's frequency cap was inert.

The one forward-looking number here: the trade tightens from **10:1 to 2.6:1** once
artifact and file limits ship. The CTA wins because there is almost nothing else on the
surface. That is worth re-testing after launch, not before.

## 5. The lever is where the wall sits

The daily image limit converts at 18% per impression and fires 71 times. The CTA
converts at 0.13% and fires 469,926 times.

Stop trying to move the 469,926.

Moving the free-tier image limit, everything else held identical:

| images per day | impressions | LR per 1k | change |
|---|---|---|---|
| 5 (today) | 71 | 5.56 | — |
| 4 | 395 | 7.16 | **+1.60** |
| 3 | 2,108 | 12.08 | **+6.52** |

Day 1 flagged this threshold as "the most actionable thing this work surfaced" and it
still is. But read section 7 before quoting any of these numbers.

Note also that the same change is worth **+29% today and +6%** after artifact and file
limits ship. If this is going to be tested, it wants testing soon.

## What CausalTwin did here, and what it did not need

Every number above comes from running the same user twice: once with an upsell
switched on, once off, with all randomness pre-drawn and indexed by opportunity so the
two runs differ by the intervention alone.

It is worth recording what this replaced. The obvious approach — log randomised
journeys, fit a model, ask it to predict what would have happened otherwise — exists
because the real world cannot rewind. A twin can. Estimating a counterfactual you are
able to execute adds error and hides the sample-size problem that turned out to be the
finding. No model was fitted and no dependency was added.

## What is solid and what is not

**Solid:** that contextual upsells effectively never co-occur on this surface, and that
the always-on CTA depresses every one of them. Both hold regardless of the exact
coefficients, because both follow from measured reach and measured frequency.

**Assumed:** the size of the CTA's drag. It is an output of the fatigue settings in
`params.py`, which were invented. Quote the direction, not the +7.06.

**Thin:** the 0.007% rests on 15 users out of 200,000. The image-limit rows rest on 71
impressions. Both want a larger run before they are defended in a room.

**Not modelled:** anger. The limit sweep assumes someone blocked at their third image
is exactly as willing to buy as someone blocked at their sixth. That cannot be true —
the daily limit converts well *because* it catches high intent, and lowering it catches
progressively less. Every number in section 5 is a ceiling, and probably a generous one.

**Also not modelled:** churn. Nothing here can see a user who gets annoyed and leaves.

## Recommendation

**Stop building the sequencing engine.** The premise does not hold on this surface. It
may hold somewhere with denser, more varied monetisation moments; it does not hold
here, and the number that says so is 0.007%.

Three next steps:

1. **Run the image-limit experiment at 3, 4 and 5**, and run it before artifact and file
   limits launch, while it is still worth 29% rather than 6%. Size it for a quarter of
   the predicted effect — roughly 560,000 users per arm. Decide it on retention and
   images generated per user, not on licence requests, because licence requests are the
   number the model already claims to know.

2. **Pre-register the impression-count prediction**: 5.6x more limit impressions at 4,
   30x at 3. That is near-pure arithmetic on usage with almost no behavioural assumption
   in it, so it is the cleanest available test of whether this twin is worth keeping.

3. **Reframe the question from order to volume.** The measurable interaction is total
   ambient pressure, not sequence. "How many commercial interruptions should this
   surface carry, and where" is answerable with the tool as built. "Which offer should
   follow which" is not a question this product asks often enough to matter.

---

*`python scripts/day2_ablation.py` · `python scripts/day2_cooccurrence.py`*
