"""Every tunable number in the simulator lives here, so calibration happens in one place.

All BETA_* coefficients are in LOG-ODDS units, not probability units.
Traits are centred before use, so a perfectly average user converts at exactly
the offer's base_rate. A coefficient of 2.0 therefore means a max-trait user
(trait = 1.0) gets +1.0 log-odds, which is ~2.7x the odds of an average user.
"""

# --- Click stage: does the prompt earn attention? ---
# This is where fatigue, novelty and cross-offer effects act.
BETA_RELEVANCE = 1.6
BETA_ENGAGEMENT = 0.8
BETA_FATIGUE = 2.5
BETA_TRUST = 1.0

# How fast a repeated creative stops registering, which is what keeps the always-on
# CTA from earning in proportion to its enormous impression count.
BETA_BLINDNESS = 0.45

# --- Licence request stage: having clicked, do they ask for a licence? ---
# Each offer carries its own measured base rate; these move it per user.
# Attention effects deliberately do not act here, to avoid counting fatigue twice.
BETA_INTENT = 2.0
BETA_PRICE_SENSITIVITY = 1.4

# Fatigue is short-term irritation and recovers while the user is left alone.
FATIGUE_HALF_LIFE_HOURS = 18.0

# Extra fatigue when an offer closely resembles the one before it, so that
# three related upsells cost more than three unrelated ones.
SIMILARITY_PENALTY = 0.8

# How fast one offer's influence on a later offer fades.
PRIMING_HALF_LIFE_HOURS = 12.0

# How long a deferred offer stays queued before the moment has passed.
DEFER_WINDOW_HOURS = 6.0

# --- Usage model, solved against measured impression volumes ---
# Both are set by calibrate.solve_usage(); the defaults are the solved values.
# ACTIVITY_INTENSITY_SCALE controls how often someone blows past a daily limit.
# CAPACITY_TRIGGER_RATE is the share of image sessions that hit GPU congestion,
# which is what makes capacity impressions scale with image usage.
ACTIVITY_INTENSITY_SCALE = 0.3142
CAPACITY_TRIGGER_RATE = 0.00736

# Expected events per active day at which an offer is half as relevant as it can be.
RELEVANCE_REFERENCE = 0.5

# Trust is long-term and, unlike fatigue, never recovers within a journey.
TRUST_PRIOR = (5.0, 2.0)
TRUST_BASELINE = TRUST_PRIOR[0] / sum(TRUST_PRIOR)
TRUST_EROSION = 0.02
