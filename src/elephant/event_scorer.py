"""Score events by nostalgia weights for digest ranking."""

from elephant.data.models import Event, NostalgiaWeights


def score_event(event: Event, weights: NostalgiaWeights) -> float:
    """Score an event for digest ranking.

    score = event.nostalgia_score
          x type_weight (milestones or mundane_daily from preferences)
          + people_boost (people_focus x len(people)/3)
          + location_boost (location_focus if location else 0)
    """
    # Type weight: milestones for milestone/celebration, mundane_daily for others
    if event.type in ("milestone", "celebration"):
        type_weight = weights.milestones
    else:
        type_weight = weights.mundane_daily

    base = event.nostalgia_score * type_weight
    people_boost = weights.people_focus * (len(event.people) / 3.0)
    location_boost = weights.location_focus if event.location else 0.0

    return base + people_boost + location_boost
