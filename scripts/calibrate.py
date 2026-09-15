"""One-off calibration against the measured 30-day window.

Run with:  python scripts/calibrate.py

Every dashboard figure counts unique users, so everything here is measured per user.
Solves reach and both funnel stages, then prints the values to paste into
causaltwin/params.py and causaltwin/offers.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from causaltwin import calibrate, offers, params, users

BASELINE_USERS = 40_000
SCAN_USERS = 1_000_000
DAYS = offers.MEASURED_DAYS


def report(title, baseline, concentrated):
    print(f"\n{title}")
    print(f"  {'entry point':<22} {'ever clicked':>20} {'click -> LR':>20} {'sample':>8}")
    for offer_id in offers.MEASURED:
        target = offers.measured_rates(offer_id)
        source = baseline if offer_id == "persistent_cta" else concentrated
        got = source.get(offer_id, {})
        print(f"  {offer_id:<22} "
              f"{got.get('ctr', 0):>9.2%} vs {target['ctr']:>7.2%} "
              f"{got.get('lr_given_click', 0):>9.1%} vs {target['lr_given_click']:>7.1%} "
              f"{got.get('seen', 0):>8,}")


def main():
    print(f"Monthly active users implied by the CTA: {offers.MONTHLY_ACTIVE_USERS:,}")

    print("\nSolving the usage model against measured reach...")
    scale, capacity_rate = calibrate.solve_usage()
    print(f"  ACTIVITY_INTENSITY_SCALE = {scale:.4f}")
    print(f"  CAPACITY_TRIGGER_RATE    = {capacity_rate:.5f}")
    params.ACTIVITY_INTENSITY_SCALE = scale
    params.CAPACITY_TRIGGER_RATE = capacity_rate

    print(f"\nScanning {SCAN_USERS:,} users to collect the ones a trigger actually reaches...")
    concentrated, scanned = calibrate.concentrate(SCAN_USERS, n_days=DAYS, seed=101)
    print(f"  kept {len(concentrated):,} of {scanned:,} "
          f"({len(concentrated) / scanned:.2%} trigger something)")

    baseline = users.generate_population(BASELINE_USERS, seed=11, n_days=DAYS)
    print("\nSimulated reach vs measured:")
    achieved = calibrate.reach(
        users.generate_population(200_000, seed=7, n_days=DAYS, with_outcome=False)
    )
    for offer_id, target in offers.REACH_TARGETS.items():
        print(f"  {offer_id:<22} {achieved[offer_id]:>8.3%} vs {target:.3%}")

    report("Before calibration, using the measured rates as raw inputs:",
           calibrate.observed_rates(baseline, "today"),
           calibrate.observed_rates(concentrated, "today"))

    print("\nSolving cold per-impression rates...")
    solved = calibrate.solve_rates(baseline, concentrated, "today", iterations=6)
    for offer_id, fields in solved.items():
        print(f"  {offer_id:<22} click_rate = {fields['click_rate']:.5f}   "
              f"lr_rate = {fields['lr_rate']:.5f}")

    holdout_baseline = users.generate_population(BASELINE_USERS, seed=42, n_days=DAYS)
    holdout_concentrated, _ = calibrate.concentrate(SCAN_USERS, n_days=DAYS, seed=999)
    report("Held-out check on unseen users:",
           calibrate.observed_rates(holdout_baseline, "today"),
           calibrate.observed_rates(holdout_concentrated, "today"))

    print("\n  Reach is what the volumes pin down. The split between how often people")
    print("  generate images and how often the GPU is busy is not measured; only")
    print("  their product is.")
    print(f"  simulated share of users who ever generate an image: {achieved['image_any']:.1%}")


if __name__ == "__main__":
    main()
