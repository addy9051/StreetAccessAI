"""StreetAccess configuration.

All threshold values defined here are provisional hypotheses, NOT evidence-backed constants.
They represent initial engineering assumptions for MVP prototyping and must be tuned
against calibrated real-world measurements and pedestrian usability studies.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProvisionalThresholds:
    """Provisional matching, freshness, and routing thresholds.
    
    NOTE: These values are PROVISIONAL HYPOTHESES, not evidence-backed constants.
    """
    # Spatial matching hypothesis: Points within 15 meters may associate to a pedestrian segment.
    SPATIAL_MATCH_DISTANCE_THRESHOLD_METERS: float = 15.0

    # Ambiguity hypothesis: If the distance difference between the two nearest segments
    # is less than 5 meters, the match is considered AMBIGUOUS rather than CONFIDENT.
    SPATIAL_AMBIGUITY_DELTA_THRESHOLD_METERS: float = 5.0

    # Bearing tolerance hypothesis: If bearing is available, candidate segment orientation
    # should be within 45 degrees of walking/observation bearing.
    BEARING_TOLERANCE_DEGREES: float = 45.0

    # Survey freshness hypothesis: A survey older than 30 days is considered STALE_ONLY.
    SURVEY_RECENCY_HORIZON_DAYS: int = 30

    # Report staleness hypothesis: A verified report older than 60 days decays to STALE status.
    REPORT_RECENCY_HORIZON_DAYS: int = 60

    # Unverified report expiry hypothesis: Reports in pending states expire after 90 days.
    REPORT_TTL_DAYS: int = 90

    # Default walking speed hypothesis for pedestrian travel time estimation (approx. 1.2 m/s).
    DEFAULT_WALKING_SPEED_MPS: float = 1.2


CONFIG = ProvisionalThresholds()

