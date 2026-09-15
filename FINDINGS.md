# CausalTwin — Day 1 Findings

**Shiv Bisht** | 14 September 2026 | Surface: Microsoft Copilot App

---

## 1. We rank our upsells by the wrong number

Click-through rate puts our three live entry points in almost exactly the wrong order.
Looking one step further down the funnel, at who actually reaches a licence request:

| Entry point | Users reached | Ever clicked | Of those, requested a licence | **LRs per 1k monthly actives** |
|---|---|---|---|---|
| Image daily limit | 0.23% | 12.3% | **63.6%** | 0.18 |
| Image capacity | 1.60% | **15.1%** | 13.7% | 0.33 |
| Persistent CTA | 100% | 2.4% | 21.8% | **5.24** |

The capacity block wins on clicks and collapses on commitment. It draws curiosity
clicks from people who were not trying to buy — they just wanted the system to work.
The daily image limit is the reverse: someone denied a sixth image knows exactly what
they want, and two-thirds of those clicks convert into a licence request.

This is our own data. No model required.

## 2. Per impression, the persistent CTA is 60x weaker

The dashboard's 2.4% is the chance a user ever clicks the CTA across a whole month of
it being on screen. It is not the chance of clicking any one appearance.

| Entry point | Per impression | Per user reached |
|---|---|---|
| Image capacity | 16.1% | 15.1% |
| Image daily limit | 13.2% | 12.3% |
| Persistent CTA | **0.23%** | 2.4% |

The CTA does not win because it is persuasive. It wins because it is shown to
everybody, constantly. That is the entire trade on this surface, and it is invisible
if the two kinds of rate are read as the same thing.

## 3. Our best moment barely happens

The daily image limit converts far better than anything else and reaches 0.23% of
users. It produces 3% of our licence requests.

Whether the five-images-per-day threshold sits where it maximises licence requests, or
simply where it happened to land, is a real and testable question. It is the most
actionable thing this work surfaced.

## 4. A three-per-day frequency cap does nothing

Natural volume is about one impression per active day. The cap never binds — the
simulated results are identical to always-show, down to the impression. Our static cap
is not too blunt. It is inert.

## 5. "Defer" does not exist here

The proposal assumes three actions: show, delay, skip. Measured on simulated journeys,
542 deferrals occurred and **none** was ever shown later. The median gap between upsell
opportunities is **24 hours**; only 2.5% of gaps are under six.

Delaying by a few hours is identical to skipping, because there is no "a few hours
later" — there is tomorrow. Deferral on this surface has to mean days, not hours.

## What CausalTwin is

A simulated Copilot App, tuned until it reproduces our real funnel, built to do the one
thing the live product cannot: **run the same user twice.** Show them the offer, then
rewind and don't, with everything else held identical. That is the only way to answer
"would we have done better if we had skipped that one?" — the question our analytics
cannot reach, because the two events sit in different features and different teams.

## Is it trustworthy?

Calibrated against 30 days of measured data, then checked on users it was never tuned on:

| Entry point | Reach (model vs actual) | Ever clicked | Click → licence request |
|---|---|---|---|
| Image daily limit | 0.233% vs 0.228% | 14.3% vs 12.3% | 61.9% vs 63.6% |
| Image capacity | 1.595% vs 1.596% | 15.1% vs 15.1% | 16.3% vs 13.7% |
| Persistent CTA | 100% vs 100% | 2.42% vs 2.40% | 19.9% vs 21.8% |

End to end, the model produces **5.56** licence requests per 1,000 monthly actives
against a measured **5.75** — a total it was never fitted against.

The model also **contradicted its author three times.** It first argued for cutting the
persistent CTA, first rated capacity as our weakest entry point, and first treated the
CTA's 2.4% as a per-impression rate. The data reversed all three. A model that only
confirms what its author assumed does not behave that way.

## What is solid and what is not

**Measured:** reach and both funnel stages for the three live entry points.

**Assumed:** how offers affect each other, all fatigue and trust effects, and both
unlaunched limits. These are hypotheses, not findings.

**Not measured:** how often people generate images versus how often the GPU is busy.
The data fixes only the product of those two, not the split.

**Not modelled:** what share of licence requests become paid seats.

## Recommendation

No product change yet. This is a diagnosis, not a result. No policy tested — frequency
caps, enforced spacing, resting the CTA — beat what we do today.

Three next steps:

1. **The same funnel data split by month**, not pooled, so we can calibrate on one
   month and predict the next blind. That would be the first genuine out-of-sample test.
2. **A rough estimate of how many users the artifact and file limits will reach.** My
   assumption implies 30x the image limit's reach, and it drives the entire launch
   comparison on its own.
3. **Learn how offers affect each other** instead of assuming it. This is the untested
   core of the idea.

---

*Working prototype, 34 tests passing.* `python scripts/day1_demo.py`
