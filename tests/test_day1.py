import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import math

import dataclasses

import numpy as np
import pytest

from causaltwin import calibrate, journey, offers, params, scm, usage, users


@pytest.fixture(scope="module")
def population():
    return users.generate_population(n_users=3_000, seed=7, n_days=21)


@pytest.fixture
def restore_catalog():
    snapshot = dict(offers.OFFERS)
    yield
    offers.OFFERS.update(snapshot)


def average_user():
    row = {"user_id": 0, "segment": "casual", "trust": params.TRUST_BASELINE}
    for key in users.TRAIT_KEYS:
        row[key] = 0.5
    for activity in users.ACTIVITIES:
        # Chosen so relevance lands exactly at 0.5 and the cold rate is recovered.
        row[f"{activity}_session_rate"] = params.RELEVANCE_REFERENCE / 2.0
        row[f"{activity}_lambda"] = 1.0
    return row


def test_average_user_clicks_at_the_offers_cold_rate():
    user = average_user()
    state = scm.initial_state(user)
    for offer in offers.OFFERS.values():
        if offer.driver is None:
            continue
        assert scm.click_probability(user, offer, state, 0.0) == pytest.approx(
            offer.click_rate, abs=1e-9
        )


def test_average_user_requests_at_the_offers_cold_rate():
    user = average_user()
    for offer in offers.OFFERS.values():
        assert scm.license_request_probability(user, offer) == pytest.approx(
            offer.lr_rate, abs=1e-9
        )


def test_conversion_is_the_product_of_both_stages():
    user = average_user()
    state = scm.initial_state(user)
    offer = offers.OFFERS["image_daily_limit"]
    assert scm.conversion_probability(user, offer, state, 0.0) == pytest.approx(
        scm.click_probability(user, offer, state, 0.0)
        * scm.license_request_probability(user, offer)
    )


def test_price_sensitivity_moves_requests_but_not_clicks():
    cheapskate = dict(average_user(), price_sensitivity=0.95)
    spender = dict(average_user(), price_sensitivity=0.05)
    offer = offers.OFFERS["image_daily_limit"]
    state = scm.initial_state(cheapskate)
    assert scm.license_request_probability(cheapskate, offer) < scm.license_request_probability(
        spender, offer
    )
    assert scm.click_probability(cheapskate, offer, state, 0.0) == pytest.approx(
        scm.click_probability(spender, offer, state, 0.0)
    )


def test_capacity_wins_clicks_and_loses_commitment():
    """The measured funnel inverts between its two stages, which is the whole point."""
    capacity = offers.measured_rates("image_capacity")
    daily = offers.measured_rates("image_daily_limit")
    assert capacity["ctr"] > daily["ctr"]
    assert capacity["lr_given_click"] < daily["lr_given_click"]
    assert capacity["lr_per_user_reached"] < daily["lr_per_user_reached"]
    assert offers.OFFERS["image_capacity"].lr_rate < offers.OFFERS["image_daily_limit"].lr_rate


def test_the_cta_is_worst_per_user_and_still_most_of_the_outcome():
    rates = {offer_id: offers.measured_rates(offer_id) for offer_id in offers.MEASURED}
    worst = min(rates, key=lambda k: rates[k]["lr_per_user_reached"])
    biggest = max(offers.MEASURED, key=lambda k: offers.MEASURED[k]["license_requests"])
    assert worst == "persistent_cta"
    assert biggest == "persistent_cta"


def test_the_cta_is_far_weaker_per_impression_than_per_user():
    """2.4% is the chance of ever clicking across a month, not of clicking one banner."""
    cta = offers.OFFERS["persistent_cta"]
    assert cta.click_rate < offers.MEASURED_CTR["persistent_cta"] / 5
    for offer_id in ("image_daily_limit", "image_capacity"):
        assert offers.OFFERS[offer_id].click_rate > 20 * cta.click_rate


def test_three_entry_points_are_measured_and_two_are_not():
    measured = {offer.id for offer in offers.OFFERS.values() if offer.measured}
    assert measured == set(offers.MEASURED)
    assert measured == {"image_daily_limit", "image_capacity", "persistent_cta"}


def test_capacity_outperforms_the_daily_limit_on_clicks_only():
    """The dashboard says capacity draws more clicks but far fewer licence requests."""
    assert offers.MEASURED_CTR["image_capacity"] > offers.MEASURED_CTR["image_daily_limit"]
    assert (
        offers.MEASURED_LR_GIVEN_CLICK["image_capacity"]
        < offers.MEASURED_LR_GIVEN_CLICK["image_daily_limit"]
    )
    assert offers.OFFERS["image_capacity"].click_rate > offers.OFFERS["image_daily_limit"].click_rate


def test_the_cta_dwarfs_every_contextual_trigger_by_reach():
    assert offers.REACH_TARGETS["persistent_cta"] == 1.0
    assert offers.REACH_TARGETS["image_capacity"] < 0.02
    assert offers.REACH_TARGETS["image_daily_limit"] < 0.003


def test_probabilities_stay_in_range_under_extreme_state(population):
    state = scm.State(
        fatigue=1.0,
        trust=0.0,
        hour=0.0,
        history=(("image_daily_limit", 0.0),),
        seen_counts=(("image_capacity", 40),),
    )
    for i in range(5):
        user = population.table.iloc[i]
        for offer in offers.OFFERS.values():
            assert 0.0 < scm.click_probability(user, offer, state, 0.5) < 1.0
            assert 0.0 < scm.conversion_probability(user, offer, state, 0.5) < 1.0


def test_relevance_is_grounded_in_the_users_own_usage():
    light = dict(average_user(), image_session_rate=0.01, image_lambda=0.5)
    heavy = dict(average_user(), image_session_rate=0.60, image_lambda=3.0)
    offer = offers.OFFERS["image_daily_limit"]
    assert users.relevance(light, offer) < users.relevance(heavy, offer)
    assert (
        scm.click_probability(light, offer, scm.initial_state(light), 0.0)
        < scm.click_probability(heavy, offer, scm.initial_state(heavy), 0.0)
    )


def test_two_image_triggers_collide_but_a_different_wall_helps():
    user = average_user()
    state = scm.initial_state(user)
    capacity = offers.OFFERS["image_capacity"]
    artifact = offers.OFFERS["artifact_limit"]
    before_capacity = scm.click_probability(user, capacity, state, 0.0)
    before_artifact = scm.click_probability(user, artifact, state, 0.0)

    after = scm.after_show(user, state, offers.OFFERS["image_daily_limit"], 0.0, clicked=False)
    assert scm.click_probability(user, capacity, after, 1.0) < before_capacity
    assert scm.click_probability(user, artifact, after, 1.0) > before_artifact


def test_priming_fades_as_the_gap_grows():
    user = average_user()
    state = scm.after_show(user, scm.initial_state(user), offers.OFFERS["image_daily_limit"], 0.0, False)
    effects = [abs(scm.priming(state, "image_capacity", hour)) for hour in (1, 6, 12, 24, 48)]
    assert effects == sorted(effects, reverse=True)
    assert effects[-1] < 0.1


def test_priming_survives_more_than_one_offer_back():
    user = average_user()
    state = scm.initial_state(user)
    state = scm.after_show(user, state, offers.OFFERS["image_daily_limit"], 0.0, False)
    state = scm.after_show(user, state, offers.OFFERS["persistent_cta"], 1.0, False)
    assert scm.priming(state, "image_capacity", 2.0) < 0.0


def test_the_persistent_cta_goes_blind_with_repetition():
    user = average_user()
    state = scm.initial_state(user)
    cta = offers.OFFERS["persistent_cta"]
    first = scm.click_probability(user, cta, state, 0.0)
    for day in range(10):
        state = scm.after_show(user, state, cta, day * 24.0, False)
    assert scm.click_probability(user, cta, state, 240.0) < first / 2


def test_related_offers_cost_more_fatigue_than_unrelated_ones():
    user = average_user()
    start = scm.after_show(user, scm.initial_state(user), offers.OFFERS["image_daily_limit"], 0.0, False)
    related = scm.after_show(user, start, offers.OFFERS["image_capacity"], 1.0, False)
    unrelated = scm.after_show(user, start, offers.OFFERS["artifact_limit"], 1.0, False)
    assert related.fatigue > unrelated.fatigue


def test_fatigue_recovers_but_an_ignored_prompt_permanently_costs_trust():
    user = average_user()
    ignored = scm.after_show(user, scm.initial_state(user), offers.OFFERS["image_daily_limit"], 0.0, False)
    clicked = scm.after_show(user, scm.initial_state(user), offers.OFFERS["image_daily_limit"], 0.0, True)
    assert scm.fatigue_at(ignored, 72.0) < ignored.fatigue
    assert ignored.trust < params.TRUST_BASELINE
    assert clicked.trust == params.TRUST_BASELINE


def test_only_users_who_exceed_a_limit_see_that_upsell(population):
    for i in range(400):
        for opportunity in usage.opportunities_for(population, i, "in_two_months"):
            demand = population.demand[i, opportunity.day]
            assert population.active[i, opportunity.day]
            if opportunity.offer_id == "image_daily_limit":
                assert demand[0] > offers.LIMITS["images"]
            elif opportunity.offer_id == "artifact_limit":
                assert demand[1] > offers.LIMITS["artifacts"]
            elif opportunity.offer_id == "file_limit":
                assert demand[2] > offers.LIMITS["files"]
            elif opportunity.offer_id == "image_capacity":
                assert demand[0] >= 1
                assert population.congestion_noise[i, opportunity.day] < params.CAPACITY_TRIGGER_RATE


def test_capacity_reach_scales_with_how_many_people_generate_images():
    """Capacity is dynamic: more users generating images has to mean more reach."""
    quiet = users.generate_population(4_000, seed=9, n_days=30, session_scale=0.4)
    busy = users.generate_population(4_000, seed=9, n_days=30, session_scale=2.5)
    assert calibrate.reach(busy)["image_capacity"] > calibrate.reach(quiet)["image_capacity"]


def test_daily_limit_reach_scales_with_images_per_session():
    """The daily cap is about depth of use, not breadth, so it tracks the other lever."""
    light = users.generate_population(4_000, seed=9, n_days=30, intensity_scale=0.3)
    heavy = users.generate_population(4_000, seed=9, n_days=30, intensity_scale=3.0)
    assert calibrate.reach(heavy)["image_daily_limit"] > calibrate.reach(light)["image_daily_limit"]


def test_simulated_reach_matches_the_measured_window():
    """Needs a large sample: the daily limit reaches 0.23% of users."""
    sample = users.generate_population(150_000, seed=21, n_days=30, with_outcome=False)
    achieved = calibrate.reach(sample)
    for offer_id, target in offers.REACH_TARGETS.items():
        assert achieved[offer_id] == pytest.approx(target, rel=0.2)


def test_the_cta_funnel_reproduces_the_measured_window(population):
    """Only the CTA has enough users at this sample size to check directly."""
    rates = calibrate.observed_rates(population, "today")["persistent_cta"]
    target = offers.measured_rates("persistent_cta")
    seen = rates["seen"]
    ctr_error = math.sqrt(target["ctr"] * (1 - target["ctr"]) / seen)
    assert abs(rates["ctr"] - target["ctr"]) < max(0.005, 4 * ctr_error)


def test_concentrating_finds_the_rare_trigger_users():
    concentrated, scanned = calibrate.concentrate(40_000, chunk=20_000, seed=77, n_days=30)
    assert 0 < len(concentrated) < scanned * 0.05
    assert calibrate.triggers_contextual(concentrated, "today").all()


def test_solving_moves_both_stages_toward_the_measured_targets(restore_catalog):
    baseline = users.generate_population(4_000, seed=3, n_days=30)
    concentrated, _ = calibrate.concentrate(60_000, chunk=20_000, seed=55, n_days=30)
    for offer_id in offers.MEASURED:
        offers.OFFERS[offer_id] = dataclasses.replace(
            offers.OFFERS[offer_id], click_rate=0.05, lr_rate=0.35
        )

    def distance():
        measured = {
            "persistent_cta": calibrate.observed_rates(baseline, "today"),
            "contextual": calibrate.observed_rates(concentrated, "today"),
        }
        total = 0.0
        for offer_id in offers.MEASURED:
            source = "persistent_cta" if offer_id == "persistent_cta" else "contextual"
            got = measured[source].get(offer_id, {})
            target = offers.measured_rates(offer_id)
            total += abs(got.get("ctr", 0) - target["ctr"])
        return total

    before = distance()
    calibrate.solve_rates(baseline, concentrated, "today", iterations=4)
    assert distance() < before


def test_todays_scenario_is_a_subset_of_the_launch_scenario(population):
    for i in range(200):
        today = usage.opportunities_for(population, i, "today")
        later = usage.opportunities_for(population, i, "in_two_months")
        assert len(today) <= len(later)
        assert {o.offer_id for o in today} <= set(offers.SCENARIOS["today"])


def test_opportunity_stream_does_not_depend_on_the_policy(population):
    """The twin only holds if the chances to interrupt are fixed before we decide."""
    for i in (3, 17, 42):
        stream = usage.opportunities_for(population, i, "in_two_months")
        for policy in (journey.always_show, journey.contextual_only, journey.frequency_cap(1)):
            result = journey.run_journey(population, i, policy, "in_two_months")
            assert result.opportunities == len(stream)


def test_twin_replay_is_deterministic(population):
    first = journey.run_journey(population, 11, journey.always_show, "in_two_months")
    second = journey.run_journey(population, 11, journey.always_show, "in_two_months")
    assert first.requested == second.requested
    assert first.requested_from == second.requested_from
    assert [s.requested for s in first.steps] == [s.requested for s in second.steps]


def test_suppressing_offers_does_not_shift_luck_at_later_opportunities(population):
    result = journey.run_journey(population, 11, journey.contextual_only, "in_two_months")
    noise_row = population.outcome[11]
    for step in result.steps:
        shown = step.action is journey.Action.SHOW
        assert step.clicked == (shown and noise_row[step.index, 0] < step.click_probability)
        assert step.requested <= step.clicked


def test_deferring_collapses_into_suppressing_on_this_surface():
    """Opportunities sit about a day apart, so an offer deferred by a few hours almost
    never gets a second moment. Show, defer and suppress is really two choices here.
    """
    concentrated, _ = calibrate.concentrate(60_000, chunk=20_000, seed=31, n_days=30)
    deferred = shown_later = 0
    for i in range(len(concentrated)):
        result = journey.run_journey(concentrated, i, journey.spaced(6.0), "in_two_months")
        deferred += sum(s.action is journey.Action.DEFER for s in result.steps)
        shown_later += sum(s.deferred_from is not None for s in result.steps)
    assert deferred > 0
    assert shown_later < deferred * 0.05


def test_defer_does_resolve_when_the_window_reaches_the_next_day(monkeypatch):
    """Proves the mechanism works, and that it is the spacing of chances that kills it."""
    monkeypatch.setattr(params, "DEFER_WINDOW_HOURS", 48.0)
    concentrated, _ = calibrate.concentrate(60_000, chunk=20_000, seed=31, n_days=30)
    shown_later = 0
    for i in range(len(concentrated)):
        result = journey.run_journey(concentrated, i, journey.spaced(6.0), "in_two_months")
        shown_later += sum(s.deferred_from is not None for s in result.steps)
    assert shown_later > 0


def test_throttling_the_cta_trades_impressions_for_a_higher_click_rate(population):
    def summarise(policy):
        results = [journey.run_journey(population, i, policy, "in_two_months") for i in range(600)]
        shown = np.mean([r.offers_shown for r in results])
        clicks = np.mean([r.clicks for r in results])
        return shown, clicks / shown

    full_shown, full_ctr = summarise(journey.always_show)
    rested_shown, rested_ctr = summarise(journey.throttle_persistent(168.0))
    assert rested_shown < full_shown
    assert rested_ctr > full_ctr


def test_a_three_per_day_cap_is_inert_on_this_surface(population):
    """Natural volume is about one impression per active day, so the cap never binds."""
    capped = [journey.run_journey(population, i, journey.frequency_cap(3), "in_two_months") for i in range(400)]
    everything = [journey.run_journey(population, i, journey.always_show, "in_two_months") for i in range(400)]
    assert [r.offers_shown for r in capped] == [r.offers_shown for r in everything]


def test_segments_are_sampled_not_derived(population):
    table = population.table
    assert set(table["segment"]) == set(users.SEGMENTS)
    assert population.outcome.shape[1] >= max(
        len(usage.opportunities_for(population, i, "in_two_months")) for i in range(400)
    )
    assert population.outcome.shape[2] == 2
    creators = table.loc[table["segment"] == "creator", "image_session_rate"]
    workers = table.loc[table["segment"] == "knowledge_worker", "image_session_rate"]
    assert creators.mean() > workers.mean()
    assert workers.max() > creators.min()
