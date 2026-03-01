"""Score memories by nostalgia weights for digest ranking."""

from elephant.data.models import Memory, NostalgiaWeights


def score_memory(memory: Memory, weights: NostalgiaWeights) -> float:
    """Score a memory for digest ranking.

    score = memory.nostalgia_score
          x type_weight (milestones or mundane_daily from preferences)
          + people_boost (people_focus x len(people)/3)
          + location_boost (location_focus if location else 0)
    """
    # Type weight: milestones for milestone/celebration, mundane_daily for others
    if memory.type in ("milestone", "celebration"):
        type_weight = weights.milestones
    else:
        type_weight = weights.mundane_daily

    base = memory.nostalgia_score * type_weight
    people_boost = weights.people_focus * (len(memory.people) / 3.0)
    location_boost = weights.location_focus if memory.location else 0.0

    return base + people_boost + location_boost


