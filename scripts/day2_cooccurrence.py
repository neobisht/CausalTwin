"""How often do two different contextual upsells land close enough to interact?

Run with:  python scripts/day2_cooccurrence.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from causaltwin import offers, usage, users

N_USERS = 200_000
SCENARIO = "in_two_months"

population = users.generate_population(
    n_users=N_USERS, seed=42, n_days=offers.MEASURED_DAYS, with_outcome=False
)

both = close = 0
for i in range(N_USERS):
    stream = [o for o in usage.opportunities_for(population, i, SCENARIO)
              if offers.OFFERS[o.offer_id].contextual]
    if len({o.offer_id for o in stream}) < 2:
        continue
    both += 1
    if any(b.hour - a.hour <= 24.0 and a.offer_id != b.offer_id
           for a, b in zip(stream, stream[1:])):
        close += 1

print(f"users: {N_USERS:,}")
print(f"2+ different contextual offers: {both:>6,}  ({both / N_USERS:.3%})")
print(f"two of them inside 24h:         {close:>6,}  ({close / N_USERS:.3%})")