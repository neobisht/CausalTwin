"""Walks a user through their upsell opportunities under a decision policy."""

from dataclasses import dataclass, field
from enum import Enum

from . import offers, params, scm, usage, users


class Action(str, Enum):
    SHOW = "show"
    DEFER = "defer"
    SUPPRESS = "suppress"


@dataclass
class Step:
    index: int
    hour: float
    day: int
    offer_id: str
    reason: str
    action: Action
    click_probability: float
    clicked: bool
    requested: bool
    deferred_from: str | None = None


@dataclass
class JourneyResult:
    user_id: int
    segment: str
    requested: bool
    requested_from: str | None
    opportunities: int
    offers_shown: int
    clicks: int
    final_fatigue: float
    final_trust: float
    steps: list = field(default_factory=list)


def run_journey(population: users.Population, i: int, policy, scenario: str = "in_two_months"):
    user = population.table.iloc[i]
    noise_row = population.outcome[i]
    stream = usage.opportunities_for(population, i, scenario)

    state = scm.initial_state(user)
    steps: list[Step] = []
    requested = False
    requested_from: str | None = None
    pending: tuple[str, float] | None = None

    for opportunity in stream:
        offer_id, deferred_from = opportunity.offer_id, None

        # A deferred offer takes over the next moment the user gives us, provided
        # the moment it belonged to has not already gone stale.
        if pending is not None:
            queued_id, queued_hour = pending
            pending = None
            if opportunity.hour - queued_hour <= params.DEFER_WINDOW_HOURS:
                offer_id, deferred_from = queued_id, opportunity.offer_id

        offer = offers.OFFERS[offer_id]
        action = policy(user, state, offer, opportunity)

        click_p = 0.0
        clicked = False
        if action is Action.SHOW:
            click_p = scm.click_probability(user, offer, state, opportunity.hour)
        elif action is Action.DEFER:
            pending = (offer_id, opportunity.hour)

        # Noise is indexed by opportunity, never by how many offers were shown.
        # Suppressing an early offer therefore cannot shift the user's luck later,
        # which is what makes two runs genuine counterfactuals of each other.
        click_noise, request_noise = noise_row[opportunity.index]
        if action is Action.SHOW:
            clicked = bool(click_noise < click_p)
            requested = bool(
                clicked and request_noise < scm.license_request_probability(user, offer)
            )
        else:
            requested = False

        steps.append(Step(
            index=opportunity.index,
            hour=opportunity.hour,
            day=opportunity.day,
            offer_id=offer_id,
            reason=opportunity.reason,
            action=action,
            click_probability=click_p,
            clicked=clicked,
            requested=requested,
            deferred_from=deferred_from,
        ))

        if action is Action.SHOW:
            state = scm.after_show(user, state, offer, opportunity.hour, clicked)
        if requested:
            requested_from = offer_id
            break

    return JourneyResult(
        user_id=int(user["user_id"]),
        segment=str(user["segment"]),
        requested=requested,
        requested_from=requested_from,
        opportunities=len(stream),
        offers_shown=sum(step.action is Action.SHOW for step in steps),
        clicks=sum(step.clicked for step in steps),
        final_fatigue=state.fatigue,
        final_trust=state.trust,
        steps=steps,
    )


def always_show(user, state, offer, opportunity):
    return Action.SHOW


def contextual_only(user, state, offer, opportunity):
    """Drop the persistent CTA and keep only the triggered upsells."""
    return Action.SHOW if offer.contextual else Action.SUPPRESS


def throttle_persistent(min_gap_hours: float = 48.0):
    """Keep every triggered upsell, but rest the always-on CTA between appearances.

    The CTA carries almost all the impressions on this surface, so its refresh rate
    is the single largest lever available without touching the contextual triggers.
    """
    def policy(user, state, offer, opportunity):
        if offer.contextual:
            return Action.SHOW
        seen = [hour for offer_id, hour in state.history if offer_id == "persistent_cta"]
        if seen and opportunity.hour - seen[-1] < min_gap_hours:
            return Action.SUPPRESS
        return Action.SHOW
    return policy


def frequency_cap(max_per_day: int = 3):
    """The static baseline: one rule for every user, every offer, every situation."""
    def policy(user, state, offer, opportunity):
        today = [h for _, h in state.history if opportunity.hour - h < 24.0]
        return Action.SHOW if len(today) < max_per_day else Action.SUPPRESS
    return policy


def spaced(min_gap_hours: float = 6.0, defer_window: float = 2.0):
    """Enforces breathing room, and defers rather than drops when the gap is close.

    Uses only what a live system can observe: time since the last offer. It never
    reads the interference matrix, so beating always-show here is a fair result.
    """
    def policy(user, state, offer, opportunity):
        if not state.history:
            return Action.SHOW
        gap = opportunity.hour - state.history[-1][1]
        if gap >= min_gap_hours:
            return Action.SHOW
        if gap >= min_gap_hours - defer_window:
            return Action.DEFER
        return Action.SUPPRESS
    return policy

