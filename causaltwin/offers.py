"""The Microsoft Copilot App upsell surface.

Every upsell here sells the same thing: a Copilot premium subscription. That single
fact drives most of the interesting behaviour. Showing a fourth upsell cannot earn
a fourth sale, but it does cost a fourth dose of irritation, so the marginal value
of each extra interruption falls while its marginal cost does not.
"""

import math
from dataclasses import dataclass

# Free-tier ceilings in the Copilot app.
LIMITS = {"images": 5, "artifacts": 3, "files": 5}

# Fraction of requests-per-minute capacity above which the capacity upsell fires.
GPU_CAPACITY_THRESHOLD = 0.80


@dataclass(frozen=True)
class Offer:
    id: str
    label: str
    driver: str | None  # which usage dimension makes this offer relevant
    click_rate: float
    lr_rate: float
    fatigue_cost: float
    contextual: bool
    measured: bool


# Both rates are COLD: an average user, no fatigue, nothing shown before. They are
# not the dashboard ratios. Three of each are solved by scripts/calibrate.py so the
# simulation reproduces the measured 30-day funnel; artifacts and files are not live
# yet, so theirs are assumptions.
#
# No offer carries a value: all five sell the same subscription, so a licence request
# is worth the same wherever it came from.
OFFERS = {
    "image_daily_limit": Offer(
        id="image_daily_limit",
        label="Image limit (5/day reached)",
        driver="images",
        # The highest-commitment moment on the surface: of the users who ever click,
        # 64% reach the licence request. Someone denied a sixth image knows what
        # they want. Per impression it is also one of the strongest, at 13%.
        click_rate=0.13205,
        lr_rate=0.57309,
        fatigue_cost=0.11,
        contextual=True,
        measured=True,
    ),
    "image_capacity": Offer(
        id="image_capacity",
        label="Image capacity (GPU >80% RPM)",
        driver="images",
        # Best click rate on the surface and the worst commitment: only 14% of its
        # clickers reach a licence request. A busy-system message draws curiosity
        # clicks from people who were not trying to buy anything.
        click_rate=0.16097,
        lr_rate=0.10803,
        fatigue_cost=0.13,
        contextual=True,
        measured=True,
    ),
    "artifact_limit": Offer(
        id="artifact_limit",
        label="Artifact limit (3/day reached)",
        driver="artifacts",
        # Assumed to behave like the daily image limit rather than like capacity,
        # because it is also a hard cap hit mid-task.
        click_rate=0.110,
        lr_rate=0.500,
        fatigue_cost=0.10,
        contextual=True,
        measured=False,
    ),
    "file_limit": Offer(
        id="file_limit",
        label="File upload limit (5/day reached)",
        driver="files",
        click_rate=0.095,
        lr_rate=0.450,
        fatigue_cost=0.10,
        contextual=True,
        measured=False,
    ),
    "persistent_cta": Offer(
        id="persistent_cta",
        label="Persistent CTA (bottom right)",
        driver=None,
        # 0.23% per impression, against 13-16% for the triggered upsells. The 2.4% on
        # the dashboard is the chance of ever clicking across a month of appearances,
        # not the chance of clicking any one of them.
        click_rate=0.00228,
        lr_rate=0.16897,
        fatigue_cost=0.015,
        contextual=False,
        measured=True,
    ),
}

# Measured 30-day window. Every figure is a count of UNIQUE USERS, not impressions:
# "seen" is users the upsell was rendered to, "clicked" is users who clicked it at
# least once, "license_requests" is users who reached the licence-request CTA.
# So 12.3% means 12.3% of the users who hit the image limit ever clicked, across all
# the times they hit it. The per-impression rate is far lower and is not observable here.
MEASURED = {
    "image_daily_limit": {"seen": 123_100, "clicked": 15_100, "license_requests": 9_600},
    "image_capacity": {"seen": 863_700, "clicked": 130_200, "license_requests": 17_800},
    "persistent_cta": {"seen": 54_100_000, "clicked": 1_300_000, "license_requests": 283_500},
}
MEASURED_DAYS = 30

# The CTA renders to everyone who opens the app, so its unique-user count is the
# monthly active base and every other reach figure is a share of it.
MONTHLY_ACTIVE_USERS = MEASURED["persistent_cta"]["seen"]

MEASURED_CTR = {k: v["clicked"] / v["seen"] for k, v in MEASURED.items()}
MEASURED_LR_GIVEN_CLICK = {k: v["license_requests"] / v["clicked"] for k, v in MEASURED.items()}


def measured_rates(offer_id: str) -> dict[str, float]:
    """Observed user-level ratios plus their sampling error, so precision can be told
    apart from month-to-month drift. Pooling windows shrinks the first and hides the second.
    """
    stats = MEASURED[offer_id]
    ctr = stats["clicked"] / stats["seen"]
    lr_given_click = stats["license_requests"] / stats["clicked"]
    return {
        "reach": stats["seen"] / MONTHLY_ACTIVE_USERS,
        "ctr": ctr,
        "ctr_se": math.sqrt(ctr * (1 - ctr) / stats["seen"]),
        "lr_given_click": lr_given_click,
        "lr_given_click_se": math.sqrt(lr_given_click * (1 - lr_given_click) / stats["clicked"]),
        "lr_per_user_reached": stats["license_requests"] / stats["seen"],
        "lr_per_1k_active": stats["license_requests"] / MONTHLY_ACTIVE_USERS * 1_000,
    }


# Share of monthly active users each upsell reaches at least once.
REACH_TARGETS = {
    offer_id: stats["seen"] / MONTHLY_ACTIVE_USERS
    for offer_id, stats in MEASURED.items()
}

# What is live today versus what ships in roughly two months.
SCENARIOS = {
    "today": ("image_daily_limit", "image_capacity", "persistent_cta"),
    "in_two_months": (
        "image_daily_limit",
        "image_capacity",
        "artifact_limit",
        "file_limit",
        "persistent_cta",
    ),
}

CAPABILITY = {
    "image_daily_limit": "image",
    "image_capacity": "image",
    "artifact_limit": "artifacts",
    "file_limit": "files",
    "persistent_cta": "ambient",
}


def similarity(offer_id_a: str, offer_id_b: str) -> float:
    """How alike two upsells feel, from 0.0 (unrelated) to 1.0 (the same thing twice)."""
    a, b = CAPABILITY[offer_id_a], CAPABILITY[offer_id_b]
    if a == b:
        return 1.0
    if "ambient" in (a, b):
        return 0.35
    if {a, b} == {"artifacts", "files"}:
        return 0.60
    # Never zero: on this surface every upsell still points at the same subscription.
    return 0.30


# Ground truth the policy is not allowed to read. Day 2's job is to recover it from
# simulated journeys alone. Units are LOG-ODDS applied to the later offer, faded by
# the gap between them. Keys read (earlier_offer, later_offer).
INTERFERENCE = {
    # Two image walls close together reads as being punished twice for one behaviour.
    # Unverified: both triggers are driven by the same image usage, so they co-occur
    # often enough that this is the highest-value pair to measure for real.
    ("image_daily_limit", "image_capacity"): -1.10,
    ("image_capacity", "image_daily_limit"): -0.90,

    # Hitting a different kind of wall demonstrates genuine breadth of need, and that
    # has to be able to outweigh the irritation of a recent prompt or the effect is
    # invisible: fatigue alone costs roughly 0.27 log-odds an hour after an offer.
    ("image_daily_limit", "artifact_limit"): +0.55,
    ("image_daily_limit", "file_limit"): +0.50,
    ("artifact_limit", "image_daily_limit"): +0.45,
    ("artifact_limit", "file_limit"): +0.70,
    ("file_limit", "artifact_limit"): +0.65,

    # A capacity message frames the product as unreliable rather than valuable.
    ("image_capacity", "artifact_limit"): -0.35,
    ("image_capacity", "file_limit"): -0.35,
    ("image_capacity", "persistent_cta"): -0.30,

    # Declining a contextual offer makes the ambient CTA dead weight for a while.
    ("image_daily_limit", "persistent_cta"): -0.60,
    ("artifact_limit", "persistent_cta"): -0.55,
    ("file_limit", "persistent_cta"): -0.55,

    # The always-on CTA erodes the novelty of a contextual prompt.
    ("persistent_cta", "image_daily_limit"): -0.15,
    ("persistent_cta", "artifact_limit"): -0.15,
    ("persistent_cta", "file_limit"): -0.15,
    ("persistent_cta", "image_capacity"): -0.20,
}
