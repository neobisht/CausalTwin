"""Day 2: switch one upsell off and replay the same users.

Run with:  python scripts/day2_ablation.py

Journeys are driven by pre-drawn noise indexed by opportunity, so a run with an offer
suppressed is a genuine counterfactual of the baseline rather than a fresh roll.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from causaltwin import calibrate, journey, offers, usage, users

N_USERS = 10_000
N_DAYS = offers.MEASURED_DAYS
SCENARIO = "in_two_months"

def measure(population, policy, scenario):
    """Per-offer impressions and click rates, plus the licence requests they produced."""
    live = calibrate.active_users(population)
    shown, clicked = {}, {}
    requests = impressions = total = 0

    for i in range(len(population)):
        if not live[i]:
            continue
        total += 1
        result = journey.run_journey(population, i, policy, scenario)
        requests += result.requested
        for step in result.steps:
            if step.action is not journey.Action.SHOW:
                continue
            impressions += 1
            shown[step.offer_id] = shown.get(step.offer_id, 0) + 1
            if step.clicked:
                clicked[step.offer_id] = clicked.get(step.offer_id, 0) + 1

    return {
        "users": total,
        "impressions_per_user": impressions / total,
        "lr_per_1k": requests / total * 1_000,
        "shown": shown,
        "ctr": {k: clicked.get(k, 0) / v for k, v in shown.items()},
    }


if __name__ == "__main__":
    population = users.generate_population(n_users=N_USERS, seed=42, n_days=N_DAYS)
    base = measure(population, journey.always_show, SCENARIO)

    print(f"users          {base['users']:,}")
    print(f"impressions/u  {base['impressions_per_user']:.1f}")
    print(f"LR per 1k      {base['lr_per_1k']:.2f}\n")
    for offer_id, count in base["shown"].items():
        print(f"  {offer_id:<20} {count:>10,} impressions   "
              f"{base['ctr'][offer_id]:>7.2%} CTR")


    print(f"\n{'offer switched off':<22} {'impr/u':>8} {'LR per 1k':>11} {'change':>9}")
    for offer_id in offers.SCENARIOS[SCENARIO]:
        m = measure(population, journey.without(offer_id), SCENARIO)
        print(f"{offer_id:<22} {m['impressions_per_user']:>8.1f} "
              f"{m['lr_per_1k']:>11.2f} {m['lr_per_1k'] - base['lr_per_1k']:>+9.2f}")
        for other in offers.SCENARIOS[SCENARIO]:
            if other == offer_id:
                continue
            was, now = base["ctr"][other], m["ctr"].get(other, 0.0)
            print(f"    {other:<24} CTR {was:>7.2%} -> {now:>7.2%}  "
                  f"({now - was:>+.2%}, n={m['shown'].get(other, 0):,})")
    
    

    print(f"\n{'policy':<26} {'impr/u':>8} {'LR per 1k':>11} {'change':>9}")
    print(f"{'always show':<26} {base['impressions_per_user']:>8.1f} "
          f"{base['lr_per_1k']:>11.2f} {0.0:>+9.2f}")
    for quiet in (24.0, 48.0, 168.0):
        m = measure(population, journey.rest_after_contextual(quiet), SCENARIO)
        print(f"{'CTA rests ' + str(int(quiet)) + 'h':<26} {m['impressions_per_user']:>8.1f} "
              f"{m['lr_per_1k']:>11.2f} {m['lr_per_1k'] - base['lr_per_1k']:>+9.2f}")
        for other in ("image_daily_limit", "image_capacity"):
            was, now = base["ctr"][other], m["ctr"].get(other, 0.0)
            print(f"    {other:<24} CTR {was:>7.2%} -> {now:>7.2%}  "
                  f"({now - was:>+.2%}, n={m['shown'].get(other, 0):,})")

    
    print(f"\n{'image limit':<26} {'impressions':>12} {'LR per 1k':>11} {'change':>9}")
    original = offers.LIMITS["images"]
    for limit in (2, 3, 4, 5):
        offers.LIMITS["images"] = limit
        m = measure(population, journey.always_show, SCENARIO)
        print(f"{'limit = ' + str(limit):<26} {m['shown'].get('image_daily_limit', 0):>12,} "
              f"{m['lr_per_1k']:>11.2f} {m['lr_per_1k'] - base['lr_per_1k']:>+9.2f}")
    offers.LIMITS["images"] = original



    both = close = 0
    for i in range(len(population)):
        stream = [o for o in usage.opportunities_for(population, i, SCENARIO)
                  if offers.OFFERS[o.offer_id].contextual]
        if len({o.offer_id for o in stream}) < 2:
            continue
        both += 1
        if any(b.hour - a.hour <= 24.0 and a.offer_id != b.offer_id
               for a, b in zip(stream, stream[1:])):
            close += 1
    print(f"\nusers seeing 2+ different contextual offers: {both / len(population):.2%}")
    print(f"users with two of them inside 24h:           {close / len(population):.2%}")