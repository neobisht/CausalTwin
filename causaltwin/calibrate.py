"""Solves for model parameters that reproduce what the dashboard actually measured.

Everything here works at USER level, because that is what the dashboard counts. A
"seen" is a user the upsell reached at least once in 30 days, and a "clicked" is a
user who clicked at least once across every time they saw it. Per-impression rates
are not observable from that data, so nothing is calibrated against them.

Two calibrations, in order:

1. Reach. How many users each trigger touches at all, as a share of monthly actives.
   This is pure arithmetic on simulated usage and needs no journeys.
2. Click and licence-request rates. A measured ratio is not a model input: 12.3% is
   what survives after fatigue, blindness and the other upsells have taken their cut,
   so the model needs the cold rate that reproduces it.
"""

import dataclasses
import math

import numpy as np

from . import journey, offers, params, users


def active_users(population: users.Population) -> np.ndarray:
    """Users who opened the app at least once, which is the dashboard's denominator."""
    return population.active.any(axis=1)


def reach(population: users.Population) -> dict[str, float]:
    """Share of monthly active users each trigger touches at least once."""
    live = active_users(population)
    total = int(live.sum())
    images = population.demand[:, :, 0]
    image_days = (images >= 1) & population.active
    congested = image_days & (population.congestion_noise < params.CAPACITY_TRIGGER_RATE)
    return {
        "image_daily_limit": float(
            (((images > offers.LIMITS["images"]) & population.active).any(axis=1) & live).sum() / total
        ),
        "image_capacity": float((congested.any(axis=1) & live).sum() / total),
        "image_any": float((image_days.any(axis=1) & live).sum() / total),
        "persistent_cta": 1.0,
    }


def _solve_scalar(evaluate, target, low, high, tolerance, max_iterations):
    guess = (low + high) / 2
    for _ in range(max_iterations):
        guess = (low + high) / 2
        achieved = evaluate(guess)
        if abs(achieved - target) < tolerance:
            break
        if achieved < target:
            low = guess
        else:
            high = guess
    return guess


def solve_usage(
    n_users: int = 400_000,
    seed: int = 5,
    n_days: int = offers.MEASURED_DAYS,
    tolerance: float = 5e-6,
    max_iterations: int = 26,
) -> tuple[float, float]:
    """Return the activity scale and capacity trigger rate implied by measured reach.

    The two are independent. Whether a user ever blows past five images in a day
    depends on how heavy their image sessions are; whether they ever meet congestion
    depends only on how often they generate images at all and how busy the system is.

    Needs a large population because the daily limit reaches 0.23% of users, so a
    normal-sized sample contains too few of them to solve against. Journeys are not
    simulated here, so the population is generated without outcome noise.

    Note what this does not determine. Capacity reach fixes only the product of the
    image-session rate and the congestion rate; the split between them comes from the
    session rates in users.SEGMENTS, which are assumed. Halving those rates would
    roughly double the solved congestion rate and fit the data equally well.
    """
    def daily_limit_reach(scale):
        sample = users.generate_population(
            n_users, seed, n_days, intensity_scale=scale, with_outcome=False
        )
        return reach(sample)["image_daily_limit"]

    scale = _solve_scalar(
        daily_limit_reach,
        offers.REACH_TARGETS["image_daily_limit"],
        0.02, 6.0, tolerance, max_iterations,
    )

    sample = users.generate_population(
        n_users, seed, n_days, intensity_scale=scale, with_outcome=False
    )
    live = active_users(sample)
    image_days = (sample.demand[:, :, 0] >= 1) & sample.active
    total = int(live.sum())

    def capacity_reach(rate):
        hit = (image_days & (sample.congestion_noise < rate)).any(axis=1)
        return float((hit & live).sum() / total)

    capacity_rate = _solve_scalar(
        capacity_reach,
        offers.REACH_TARGETS["image_capacity"],
        0.0, 1.0, tolerance, max_iterations,
    )
    return scale, capacity_rate


def triggers_contextual(population: users.Population, scenario: str) -> np.ndarray:
    """Users who run into at least one triggered upsell during the window."""
    enabled = set(offers.SCENARIOS[scenario])
    demand, active = population.demand, population.active
    hit = np.zeros(len(population), dtype=bool)
    if "image_daily_limit" in enabled:
        hit |= ((demand[:, :, 0] > offers.LIMITS["images"]) & active).any(axis=1)
    if "artifact_limit" in enabled:
        hit |= ((demand[:, :, 1] > offers.LIMITS["artifacts"]) & active).any(axis=1)
    if "file_limit" in enabled:
        hit |= ((demand[:, :, 2] > offers.LIMITS["files"]) & active).any(axis=1)
    if "image_capacity" in enabled:
        hit |= (
            (demand[:, :, 0] >= 1)
            & active
            & (population.congestion_noise < params.CAPACITY_TRIGGER_RATE)
        ).any(axis=1)
    return hit & active_users(population)


def concentrate(
    n_users: int = 500_000,
    chunk: int = 25_000,
    seed: int = 101,
    n_days: int = offers.MEASURED_DAYS,
    scenario: str = "today",
) -> tuple[users.Population, int]:
    """Build a population of only the users a triggered upsell actually reaches.

    Contextual triggers reach under 2% of users, so a realistic sample is almost
    entirely people the calibration can learn nothing from. Scanning in chunks and
    keeping only the ones who trigger something gets a usable sample of the rare
    cases without holding half a million journeys in memory.

    Returns the concentrated population and how many users were scanned to find it.
    """
    parts = []
    scanned = 0
    for offset in range(0, n_users, chunk):
        size = min(chunk, n_users - offset)
        sample = users.generate_population(size, seed + offset, n_days)
        mask = triggers_contextual(sample, scenario)
        if mask.any():
            parts.append(users.subset(sample, mask))
        scanned += size
    return users.concat(parts), scanned


def observed_rates(population: users.Population, scenario: str) -> dict[str, dict[str, float]]:
    """Reach, click and licence-request rates counted per user, as the dashboard does."""
    live = active_users(population)
    total = int(live.sum())
    seen: dict[str, int] = {}
    clicked: dict[str, int] = {}
    requested: dict[str, int] = {}

    for i in range(len(population)):
        if not live[i]:
            continue
        result = journey.run_journey(population, i, journey.always_show, scenario)
        saw, hit, asked = set(), set(), set()
        for step in result.steps:
            if step.action is not journey.Action.SHOW:
                continue
            saw.add(step.offer_id)
            if step.clicked:
                hit.add(step.offer_id)
            if step.requested:
                asked.add(step.offer_id)
        for offer_id in saw:
            seen[offer_id] = seen.get(offer_id, 0) + 1
        for offer_id in hit:
            clicked[offer_id] = clicked.get(offer_id, 0) + 1
        for offer_id in asked:
            requested[offer_id] = requested.get(offer_id, 0) + 1

    rates = {}
    for offer_id, count in seen.items():
        clicks = clicked.get(offer_id, 0)
        asks = requested.get(offer_id, 0)
        rates[offer_id] = {
            "seen": count,
            # Meaningless on a concentrated sample, which is not a random draw.
            "reach": count / total,
            "ctr": clicks / count,
            "lr_given_click": asks / clicks if clicks else 0.0,
            "lr_per_user_reached": asks / count,
            "lr_per_1k_active": asks / total * 1_000,
        }
    return rates


def _set_rate(offer_id: str, field: str, rate: float) -> None:
    offers.OFFERS[offer_id] = dataclasses.replace(offers.OFFERS[offer_id], **{field: rate})


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def solve_rates(
    baseline: users.Population,
    concentrated: users.Population,
    scenario: str = "today",
    iterations: int = 8,
) -> dict[str, dict[str, float]]:
    """Return cold per-impression rates that reproduce the measured user-level funnel.

    Each offer is measured where it can be measured: the always-on CTA on a plain
    random sample, the triggered upsells on the concentrated sample, because a random
    sample contains too few users who ever see them.

    The gap between a cold rate and its observed ratio is close to a constant log-odds
    shift, so a fixed point converges in a handful of passes. The shift is large and
    negative for the CTA: a user sees it on every visit, so a 2.4% chance of ever
    clicking implies a far smaller chance on any single impression.
    """
    stages = (
        ("click_rate", offers.MEASURED_CTR, "ctr"),
        ("lr_rate", offers.MEASURED_LR_GIVEN_CLICK, "lr_given_click"),
    )
    for _ in range(iterations):
        measured = {
            "persistent_cta": observed_rates(baseline, scenario),
            "contextual": observed_rates(concentrated, scenario),
        }
        for field, targets, key in stages:
            for offer_id, target in targets.items():
                source = "persistent_cta" if offer_id == "persistent_cta" else "contextual"
                observed = measured[source].get(offer_id, {}).get(key, 0.0)
                if not 0.0 < observed < 1.0:
                    continue
                current = getattr(offers.OFFERS[offer_id], field)
                shift = _logit(observed) - _logit(current)
                _set_rate(offer_id, field, _sigmoid(_logit(target) - shift))
    return {
        offer_id: {
            "click_rate": offers.OFFERS[offer_id].click_rate,
            "lr_rate": offers.OFFERS[offer_id].lr_rate,
        }
        for offer_id in offers.MEASURED
    }
