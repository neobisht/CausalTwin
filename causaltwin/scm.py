"""The structural causal model: how an upsell changes a user, and how a changed
user responds to the next one.

Everything is combined in log-odds and squashed once at the end, so effects can
never push a probability outside [0, 1] and never saturate flat.
"""

import math
from dataclasses import dataclass

from . import offers, params, users


@dataclass(frozen=True)
class State:
    """Mutable-over-time part of a user. Frozen so replaying a journey is safe."""
    fatigue: float = 0.0
    trust: float = params.TRUST_BASELINE
    hour: float = 0.0
    history: tuple = ()  # ((offer_id, hour_shown), ...)
    seen_counts: tuple = ()  # ((offer_id, times_shown), ...)


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def initial_state(user) -> State:
    return State(trust=float(user["trust"]))


def times_seen(state: State, offer_id: str) -> int:
    return dict(state.seen_counts).get(offer_id, 0)


def _decay(half_life_hours: float, elapsed_hours: float) -> float:
    return 0.5 ** (max(0.0, elapsed_hours) / half_life_hours)


def fatigue_at(state: State, hour: float) -> float:
    """Fatigue the user carries at a given time, after recovering since the last offer."""
    return state.fatigue * _decay(params.FATIGUE_HALF_LIFE_HOURS, hour - state.hour)


def priming(state: State, offer_id: str, hour: float) -> float:
    """Log-odds contributed by every earlier offer, each faded by how long ago it ran.

    Summing over the whole history rather than only the previous offer is what lets
    an effect from two or three offers back still register.
    """
    total = 0.0
    for past_id, past_hour in state.history:
        weight = offers.INTERFERENCE.get((past_id, offer_id), 0.0)
        if weight:
            total += weight * _decay(params.PRIMING_HALF_LIFE_HOURS, hour - past_hour)
    return total


def click_probability(user, offer: offers.Offer, state: State, hour: float) -> float:
    """Whether the prompt earns attention. Fatigue and cross-offer effects act here."""
    z = logit(offer.click_rate)
    z += params.BETA_RELEVANCE * (users.relevance(user, offer) - 0.5)
    z += params.BETA_ENGAGEMENT * (user["engagement"] - 0.5)
    z -= params.BETA_FATIGUE * fatigue_at(state, hour)
    z += params.BETA_TRUST * (state.trust - params.TRUST_BASELINE)
    # Banner blindness: the same creative stops registering after repeated exposure,
    # which is what makes an always-on CTA worth far less than its impression count.
    z -= params.BETA_BLINDNESS * math.log1p(times_seen(state, offer.id))
    z += priming(state, offer.id, hour)
    return sigmoid(z)


def license_request_probability(user, offer: offers.Offer) -> float:
    """Whether a click reaches the licence request. Intent and price act here.

    The base rate varies enormously by entry point: 64% for someone denied a sixth
    image, 14% for someone who clicked a busy-system message.
    """
    z = logit(offer.lr_rate)
    z += params.BETA_INTENT * (user["purchase_intent"] - 0.5)
    z -= params.BETA_PRICE_SENSITIVITY * (user["price_sensitivity"] - 0.5)
    return sigmoid(z)


def conversion_probability(user, offer: offers.Offer, state: State, hour: float) -> float:
    return click_probability(user, offer, state, hour) * license_request_probability(user, offer)


def after_show(user, state: State, offer: offers.Offer, hour: float, clicked: bool) -> State:
    resemblance = similarity_to_previous(state, offer.id)
    added = (
        offer.fatigue_cost
        * (2.0 * user["fatigue_sensitivity"])
        * (1.0 + params.SIMILARITY_PENALTY * resemblance)
    )
    fatigue = min(1.0, fatigue_at(state, hour) + added)
    # An ignored prompt is what costs trust; a click means the interruption landed.
    trust = state.trust if clicked else max(0.0, state.trust - params.TRUST_EROSION)
    counts = dict(state.seen_counts)
    counts[offer.id] = counts.get(offer.id, 0) + 1
    return State(
        fatigue=fatigue,
        trust=trust,
        hour=hour,
        history=state.history + ((offer.id, hour),),
        seen_counts=tuple(sorted(counts.items())),
    )


def similarity_to_previous(state: State, offer_id: str) -> float:
    if not state.history:
        return 0.0
    return offers.similarity(state.history[-1][0], offer_id)

