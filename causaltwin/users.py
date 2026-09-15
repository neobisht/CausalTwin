"""Synthetic Copilot App users, plus every random draw their two weeks will need.

Segment is sampled first and traits are drawn conditional on it. Deriving segments
from thresholds on traits instead would make the segment label carry no information
the traits did not already contain.

Activity is zero-inflated: most sessions involve no image generation at all. The
measured impression volumes force this. The persistent CTA is seen 439 times for
every image-limit impression, so hitting the image limit has to be a rare event.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import params

# Behavioural traits are (alpha, beta) pairs for a Beta distribution.
# session_rate is the chance an active day involves that activity at all;
# lambda is the mean number of extra events beyond the first, once it does.
SEGMENTS = {
    "creator": {
        "weight": 0.22,
        "purchase_intent": (4.0, 3.0),
        "price_sensitivity": (3.0, 3.0),
        "engagement": (6.0, 2.0),
        "fatigue_sensitivity": (3.0, 3.0),
        "image_session_rate": 0.30,
        "image_lambda": 2.5,
        "artifact_session_rate": 0.05,
        "artifact_lambda": 1.2,
        "file_session_rate": 0.06,
        "file_lambda": 1.2,
        "active_days": 0.75,
    },
    "knowledge_worker": {
        "weight": 0.28,
        "purchase_intent": (4.0, 3.0),
        "price_sensitivity": (4.0, 3.0),
        "engagement": (5.0, 2.0),
        "fatigue_sensitivity": (4.0, 3.0),
        "image_session_rate": 0.02,
        "image_lambda": 1.0,
        "artifact_session_rate": 0.22,
        "artifact_lambda": 2.2,
        "file_session_rate": 0.25,
        "file_lambda": 2.6,
        "active_days": 0.80,
    },
    "power_user": {
        "weight": 0.15,
        "purchase_intent": (6.0, 2.0),
        "price_sensitivity": (2.0, 5.0),
        "engagement": (7.0, 2.0),
        "fatigue_sensitivity": (2.0, 4.0),
        "image_session_rate": 0.15,
        "image_lambda": 2.0,
        "artifact_session_rate": 0.20,
        "artifact_lambda": 2.0,
        "file_session_rate": 0.22,
        "file_lambda": 2.4,
        "active_days": 0.90,
    },
    "casual": {
        "weight": 0.35,
        "purchase_intent": (2.0, 4.0),
        "price_sensitivity": (4.0, 3.0),
        "engagement": (2.0, 4.0),
        "fatigue_sensitivity": (3.0, 3.0),
        "image_session_rate": 0.01,
        "image_lambda": 0.8,
        "artifact_session_rate": 0.02,
        "artifact_lambda": 0.8,
        "file_session_rate": 0.02,
        "file_lambda": 0.8,
        "active_days": 0.30,
    },
}

TRAIT_KEYS = ("purchase_intent", "price_sensitivity", "engagement", "fatigue_sensitivity")
ACTIVITIES = ("image", "artifact", "file")
ACTIVITY_FOR_DRIVER = {"images": "image", "artifacts": "artifact", "files": "file"}

MAX_OPPORTUNITIES_PER_DAY = 5


@dataclass
class Population:
    """Users plus all of their pre-drawn randomness.

    Fixing every random draw up front is what turns this into a twin rather than a
    Monte Carlo simulator. The same user can be replayed under a different policy
    and any difference in outcome is caused by the policy alone.
    """
    table: pd.DataFrame
    demand: np.ndarray            # (n_users, n_days, 3) events attempted per day
    active: np.ndarray            # (n_users, n_days) did they open the app
    hour_noise: np.ndarray        # (n_users, n_days, 4) when each trigger fires
    congestion_noise: np.ndarray  # (n_users, n_days) compared against the calibrated rate
    outcome: np.ndarray           # (n_users, n_days * MAX_OPPORTUNITIES_PER_DAY, 2)
    n_days: int

    def __len__(self) -> int:
        return len(self.table)


def generate_population(
    n_users: int = 5_000,
    seed: int = 42,
    n_days: int = 14,
    intensity_scale: float | None = None,
    session_scale: float = 1.0,
    with_outcome: bool = True,
) -> Population:
    """session_scale moves how many people do an activity at all; intensity_scale moves
    how much they do once they start. Capacity reach tracks the first, daily limits
    track the second.

    with_outcome=False skips the per-opportunity noise, which is by far the largest
    array. Use it when only usage matters, such as measuring how many users a trigger
    would reach across a population too big to hold journeys for.
    """
    scale = params.ACTIVITY_INTENSITY_SCALE if intensity_scale is None else intensity_scale
    rng = np.random.default_rng(seed)

    names = list(SEGMENTS)
    weights = np.array([SEGMENTS[name]["weight"] for name in names])
    weights = weights / weights.sum()
    segment_index = rng.choice(len(names), size=n_users, p=weights)

    traits = {key: np.empty(n_users) for key in TRAIT_KEYS}
    rates = {activity: np.empty(n_users) for activity in ACTIVITIES}
    lambdas = {activity: np.empty(n_users) for activity in ACTIVITIES}
    active_rate = np.empty(n_users)

    for i, name in enumerate(names):
        mask = segment_index == i
        count = int(mask.sum())
        if count == 0:
            continue
        for key in TRAIT_KEYS:
            alpha, beta = SEGMENTS[name][key]
            traits[key][mask] = rng.beta(alpha, beta, count)
        for activity in ACTIVITIES:
            # Gamma spread keeps heavy and light users inside the same segment, so the
            # label is a tendency rather than a rule.
            mean_rate = SEGMENTS[name][f"{activity}_session_rate"] * session_scale
            rates[activity][mask] = np.clip(
                rng.gamma(shape=4.0, scale=mean_rate / 4.0, size=count), 0.0, 1.0
            )
            lambdas[activity][mask] = SEGMENTS[name][f"{activity}_lambda"]
        active_rate[mask] = SEGMENTS[name]["active_days"]

    table = pd.DataFrame({
        "user_id": np.arange(n_users),
        "segment": np.asarray(names)[segment_index],
    })
    for key in TRAIT_KEYS:
        table[key] = traits[key]
    for activity in ACTIVITIES:
        table[f"{activity}_session_rate"] = rates[activity]
        table[f"{activity}_lambda"] = lambdas[activity]
    table["active_rate"] = active_rate
    table["trust"] = rng.beta(*params.TRUST_PRIOR, n_users)

    columns = []
    for activity in ACTIVITIES:
        happens = rng.random((n_users, n_days)) < rates[activity][:, None]
        extra = rng.poisson(
            np.repeat((lambdas[activity] * scale)[:, None], n_days, axis=1)
        )
        columns.append(np.where(happens, 1 + extra, 0))
    demand = np.stack(columns, axis=2)

    active = rng.random((n_users, n_days)) < active_rate[:, None]
    hour_noise = rng.random((n_users, n_days, 4))
    congestion_noise = rng.random((n_users, n_days))
    outcome = (
        rng.random((n_users, n_days * MAX_OPPORTUNITIES_PER_DAY, 2))
        if with_outcome
        else np.empty((n_users, 0, 2))
    )

    return Population(table, demand, active, hour_noise, congestion_noise, outcome, n_days)


def subset(population: Population, mask: np.ndarray) -> Population:
    table = population.table.loc[mask].reset_index(drop=True)
    table["user_id"] = np.arange(len(table))
    return Population(
        table=table,
        demand=population.demand[mask],
        active=population.active[mask],
        hour_noise=population.hour_noise[mask],
        congestion_noise=population.congestion_noise[mask],
        outcome=population.outcome[mask],
        n_days=population.n_days,
    )


def concat(parts: list[Population]) -> Population:
    table = pd.concat([part.table for part in parts], ignore_index=True)
    table["user_id"] = np.arange(len(table))
    return Population(
        table=table,
        demand=np.concatenate([part.demand for part in parts]),
        active=np.concatenate([part.active for part in parts]),
        hour_noise=np.concatenate([part.hour_noise for part in parts]),
        congestion_noise=np.concatenate([part.congestion_noise for part in parts]),
        outcome=np.concatenate([part.outcome for part in parts]),
        n_days=parts[0].n_days,
    )


def relevance(user, offer) -> float:
    """How much this user's own behaviour makes the offer feel warranted, in [0, 1).

    Grounded in how often they run into that activity rather than an invented
    interest score, so a heavy image generator scores high on image upsells.
    """
    if offer.driver is None:
        return float(user["engagement"])
    activity = ACTIVITY_FOR_DRIVER[offer.driver]
    expected = float(user[f"{activity}_session_rate"]) * (1.0 + float(user[f"{activity}_lambda"]))
    return expected / (expected + params.RELEVANCE_REFERENCE)
