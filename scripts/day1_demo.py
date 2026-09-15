"""Day 1 demo for the Microsoft Copilot App surface.

Run with:  python scripts/day1_demo.py
Calibration lives in scripts/calibrate.py and is already baked into the parameters.

Every dashboard figure counts unique users, so every rate here is per user over the
same 30-day window the measurements cover.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from causaltwin import calibrate, journey, offers, params, scm, users

N_USERS = 25_000
N_DAYS = offers.MEASURED_DAYS


def rule(title):
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


def evaluate(population, policy, scenario):
    live = calibrate.active_users(population)
    results = [
        journey.run_journey(population, i, policy, scenario)
        for i in range(len(population)) if live[i]
    ]
    return {
        "shown": np.mean([r.offers_shown for r in results]),
        "clicked_any": np.mean([r.clicks > 0 for r in results]),
        "lr_per_1k": np.mean([r.requested for r in results]) * 1_000,
        "trust": np.mean([r.final_trust for r in results]),
    }


def main():
    population = users.generate_population(n_users=N_USERS, seed=42, n_days=N_DAYS)

    rule("STEP 1  The measured funnel, counted in unique users over 30 days")
    print(f"  Monthly active users implied by the CTA: {offers.MONTHLY_ACTIVE_USERS:,}\n")
    print(f"  {'entry point':<34} {'reach':>8} {'ever clicked':>13} "
          f"{'click -> LR':>12} {'LR per 1k MAU':>14}")
    for offer_id in offers.MEASURED:
        r = offers.measured_rates(offer_id)
        print(f"  {offers.OFFERS[offer_id].label:<34} {r['reach']:>8.2%} "
              f"{r['ctr']:>13.2%} {r['lr_given_click']:>12.1%} {r['lr_per_1k_active']:>14.2f}")
    print("\n  The capacity block wins clicks and loses commitment. The daily limit is")
    print("  the reverse. And the CTA, worst on both rates, still produces 91% of all")
    print("  licence requests because it reaches everybody.")

    rule("STEP 2  What that looks like per impression")
    print("  A user sees the CTA on every visit, so a 2.4% chance of ever clicking it")
    print("  across a month is a much smaller chance of clicking any single one.\n")
    print(f"  {'entry point':<34} {'per impression':>15} {'per user reached':>18}")
    for offer_id in offers.MEASURED:
        print(f"  {offers.OFFERS[offer_id].label:<34} "
              f"{offers.OFFERS[offer_id].click_rate:>15.2%} "
              f"{offers.measured_rates(offer_id)['ctr']:>18.2%}")
    print("\n  Per impression the CTA is roughly 60x weaker than a triggered upsell.")
    print("  It wins on volume alone, and that is the whole trade on this surface.")

    rule("STEP 3  Calibration held out")
    print(f"  These {N_USERS:,} users were not used to fit anything.\n")
    achieved = calibrate.reach(population)
    print(f"  {'entry point':<34} {'reach (sim vs real)':>26}")
    for offer_id, target in offers.REACH_TARGETS.items():
        print(f"  {offers.OFFERS[offer_id].label:<34} "
              f"{achieved[offer_id]:>13.3%} vs {target:>9.3%}")
    observed = calibrate.observed_rates(population, "today")
    print(f"\n  {'entry point':<34} {'ever clicked':>22}")
    for offer_id in offers.MEASURED:
        got = observed.get(offer_id, {})
        print(f"  {offers.OFFERS[offer_id].label:<34} "
              f"{got.get('ctr', 0):>9.2%} vs {offers.measured_rates(offer_id)['ctr']:>7.2%}"
              f"   (n={got.get('seen', 0):,})")
    print("\n  The daily limit reaches 0.23% of users, so a sample this size holds only")
    print("  a few dozen of them. scripts/calibrate.py concentrates on those users to")
    print("  fit that rate; here it is thin by construction.")

    rule("STEP 4  The two image triggers still collide")
    image_heavy = population.table["image_session_rate"].idxmax()
    heavy = population.table.iloc[image_heavy]
    state = scm.initial_state(heavy)
    daily = offers.OFFERS["image_daily_limit"]
    capacity = offers.OFFERS["image_capacity"]
    after = scm.after_show(heavy, state, daily, 0.0, clicked=False)
    print(f"  user #{image_heavy}  segment={heavy['segment']}   (per-impression click rates)\n")
    print(f"  {'capacity upsell, never shown the limit':<42} "
          f"{scm.click_probability(heavy, capacity, state, 0.0):>8.2%}")
    for gap in (1, 3, 6, 12, 24):
        print(f"  {'capacity upsell ' + str(gap) + 'h after the daily limit':<42} "
              f"{scm.click_probability(heavy, capacity, after, float(gap)):>8.2%}")
    print("\n  Assumed, not measured. Both triggers come from the same image usage, so")
    print("  this is the pair most worth checking against real data.")

    rule("STEP 5  Policies, before and after the launch")
    header = (f"  {'policy':<24} {'impressions':>12} {'ever clicked':>13} "
              f"{'LR per 1k':>11} {'trust':>8}")
    policies = {
        "always show": journey.always_show,
        "frequency cap 3/day": journey.frequency_cap(3),
        "contextual only": journey.contextual_only,
        "CTA rested 72h": journey.throttle_persistent(72.0),
        "CTA rested 168h": journey.throttle_persistent(168.0),
    }
    scores = {}
    for scenario in ("today", "in_two_months"):
        print(f"\n  {scenario.replace('_', ' ').upper()}\n")
        print(header)
        for label, policy in policies.items():
            m = evaluate(population, policy, scenario)
            scores[(scenario, label)] = m
            print(f"  {label:<24} {m['shown']:>12.1f} {m['clicked_any']:>13.2%} "
                  f"{m['lr_per_1k']:>11.2f} {m['trust']:>8.3f}")

    measured_total = sum(
        offers.measured_rates(offer_id)["lr_per_1k_active"] for offer_id in offers.MEASURED
    )
    today = scores[("today", "always show")]
    print(f"\n  Sanity check: always-show today gives {today['lr_per_1k']:.2f} licence requests per")
    print(f"  1,000 monthly actives. The dashboard total is {measured_total:.2f}.")

    reach_artifact = float(
        ((population.demand[:, :, 1] > offers.LIMITS["artifacts"]) & population.active)
        .any(axis=1).mean()
    )
    reach_file = float(
        ((population.demand[:, :, 2] > offers.LIMITS["files"]) & population.active)
        .any(axis=1).mean()
    )
    print(f"\n  Read the launch rows with care. They assume the artifact limit reaches")
    print(f"  {reach_artifact:.0%} of users and the file limit {reach_file:.0%}, against 0.23% for the image")
    print(f"  limit. Nothing measured supports those, and they drive the entire")
    print(f"  launch comparison.")

    print(f"\n  Measured: reach and both funnel stages for the three live entry points.")
    print(f"  Assumed: the two unlaunched limits, every cross-offer effect, and the")
    print(f"  split between image usage ({achieved['image_any']:.0%} of users ever) and GPU congestion")
    print(f"  ({params.CAPACITY_TRIGGER_RATE:.2%} of image days) — only their product is measured.\n")


if __name__ == "__main__":
    main()
