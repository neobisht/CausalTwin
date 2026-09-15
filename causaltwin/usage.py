"""Turns simulated app usage into the stream of moments where an upsell could fire.

Opportunities come from what the user did, not from a fixed timetable: you only see
the image wall if you asked for a sixth image. The stream is built from pre-drawn
usage, so it stays identical across policies and the twin comparison holds.
"""

from dataclasses import dataclass

from . import offers, params, users


@dataclass(frozen=True)
class Opportunity:
    index: int
    hour: float
    day: int
    offer_id: str
    reason: str


def opportunities_for(population: users.Population, i: int, scenario: str) -> list[Opportunity]:
    enabled = set(offers.SCENARIOS[scenario])
    found: list[tuple[float, str, int, str]] = []

    for day in range(population.n_days):
        if not population.active[i, day]:
            continue

        images, artifacts, files = population.demand[i, day]
        u = population.hour_noise[i, day]
        base = day * 24.0

        if "persistent_cta" in enabled:
            found.append((base + 8.5, "persistent_cta", day, "app opened"))

        if "image_daily_limit" in enabled and images > offers.LIMITS["images"]:
            found.append((base + 10.0 + 7.0 * u[0], "image_daily_limit", day,
                          f"asked for image #{int(images)}"))

        if "artifact_limit" in enabled and artifacts > offers.LIMITS["artifacts"]:
            found.append((base + 10.0 + 7.0 * u[1], "artifact_limit", day,
                          f"asked for artifact #{int(artifacts)}"))

        if "file_limit" in enabled and files > offers.LIMITS["files"]:
            found.append((base + 10.0 + 7.0 * u[2], "file_limit", day,
                          f"uploaded file #{int(files)}"))

        # Capacity is driven by image usage, not by a daily cap: any image session can
        # run into congestion, so its volume rises and falls with image generation.
        if (
            "image_capacity" in enabled
            and images >= 1
            and population.congestion_noise[i, day] < params.CAPACITY_TRIGGER_RATE
        ):
            found.append((base + 13.0 + 3.0 * u[3], "image_capacity", day,
                          "GPU RPM above 80%"))

    found.sort(key=lambda row: row[0])
    return [
        Opportunity(index=index, hour=hour, day=day, offer_id=offer_id, reason=reason)
        for index, (hour, offer_id, day, reason) in enumerate(found)
    ]


def usage_summary(population: users.Population) -> dict:
    """Share of users who hit each limit at least once during the window."""
    limits = (offers.LIMITS["images"], offers.LIMITS["artifacts"], offers.LIMITS["files"])
    active = population.active[:, :, None]
    hits = (population.demand > limits) & active
    return {
        "images": float(hits[:, :, 0].any(axis=1).mean()),
        "artifacts": float(hits[:, :, 1].any(axis=1).mean()),
        "files": float(hits[:, :, 2].any(axis=1).mean()),
    }
