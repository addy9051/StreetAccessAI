"""Synthetic pedestrian graph and spatial primitives.

Models pedestrian sidewalks, crossings, and pathways with survey timestamps.
Calculates geodesic distances using equirectangular approximation suitable for local pedestrian scales.
"""

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from streetaccess.config import CONFIG


class SurveyStatus(str, Enum):
    """Survey recency status for a pedestrian segment."""
    UNSURVEYED = "unsurveyed"
    STALE_ONLY = "stale_only"
    RECENT_SURVEY = "recent_survey"


class PedestrianNode(BaseModel):
    """Node in pedestrian graph (intersection, curb ramp, or waypoint)."""
    node_id: str
    latitude: float
    longitude: float
    description: Optional[str] = None


class PedestrianSegment(BaseModel):
    """Directed or bidirectional pedestrian segment (sidewalk, crossing, or pathway)."""
    segment_id: str
    from_node_id: str
    to_node_id: str
    length_meters: float = Field(..., gt=0.0)
    sidewalk_side: str = Field("both", description="left, right, both, or crosswalk")
    name: str = Field(..., description="Human readable name, e.g. 'North 5th St Sidewalk'")
    last_surveyed_at_utc: Optional[str] = Field(None, description="ISO timestamp of most recent survey")
    typical_speed_mps: float = Field(default=CONFIG.DEFAULT_WALKING_SPEED_MPS, gt=0.0)

    def get_survey_status(self, now: Optional[datetime] = None) -> SurveyStatus:
        """Evaluate segment survey freshness against provisional horizon."""
        if not self.last_surveyed_at_utc:
            return SurveyStatus.UNSURVEYED
        
        current_time = now or datetime.now(timezone.utc)
        survey_dt = datetime.fromisoformat(self.last_surveyed_at_utc)
        if survey_dt.tzinfo is None:
            survey_dt = survey_dt.replace(tzinfo=timezone.utc)

        age_days = (current_time - survey_dt).total_seconds() / 86400.0
        if age_days <= CONFIG.SURVEY_RECENCY_HORIZON_DAYS:
            return SurveyStatus.RECENT_SURVEY
        return SurveyStatus.STALE_ONLY


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in meters."""
    r = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def point_to_segment_distance_meters(
    plat: float, plon: float,
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """Calculate minimum perpendicular distance from a point to a line segment in meters."""
    # Convert lat/lon degrees to local meters relative to (lat1, lon1)
    cos_lat = math.cos(math.radians(lat1))
    deg_to_m = 111320.0  # approximate meters per degree latitude

    px = (plon - lon1) * deg_to_m * cos_lat
    py = (plat - lat1) * deg_to_m

    bx = (lon2 - lon1) * deg_to_m * cos_lat
    by = (lat2 - lat1) * deg_to_m

    seg_len_sq = bx * bx + by * by
    if seg_len_sq == 0.0:
        return math.hypot(px, py)

    # Project point onto segment, clamped between 0 and 1
    t = max(0.0, min(1.0, (px * bx + py * by) / seg_len_sq))
    proj_x = t * bx
    proj_y = t * by

    return math.hypot(px - proj_x, py - proj_y)


class SyntheticPedestrianGraph:
    """In-memory pedestrian network fixture for routing and spatial matching."""

    def __init__(self) -> None:
        self.nodes: Dict[str, PedestrianNode] = {}
        self.segments: Dict[str, PedestrianSegment] = {}

    def add_node(self, node_id: str, lat: float, lon: float, description: Optional[str] = None) -> None:
        self.nodes[node_id] = PedestrianNode(
            node_id=node_id, latitude=lat, longitude=lon, description=description
        )

    def add_segment(
        self,
        segment_id: str,
        from_node_id: str,
        to_node_id: str,
        length_meters: float,
        name: str,
        sidewalk_side: str = "both",
        last_surveyed_at_utc: Optional[str] = None,
    ) -> None:
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            raise ValueError(f"Cannot add segment {segment_id}: end nodes must exist in graph.")
        self.segments[segment_id] = PedestrianSegment(
            segment_id=segment_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            length_meters=length_meters,
            name=name,
            sidewalk_side=sidewalk_side,
            last_surveyed_at_utc=last_surveyed_at_utc,
        )

    @classmethod
    def create_default_network(cls) -> "SyntheticPedestrianGraph":
        """Generate a realistic synthetic pedestrian corridor with parallel sidewalks and crossing.
        
        Corridor represents two route options:
        Route A (East corridor, recently surveyed): Main Ave East Sidewalk
        Route B (West corridor, partially unsurveyed): Main Ave West Sidewalk
        """
        graph = cls()
        # Origin / Destination
        graph.add_node("N_ORIGIN", 37.774900, -122.419400, "Corridor South Junction")
        graph.add_node("N_DEST", 37.778000, -122.419400, "Corridor North Junction")
        
        # Route 1: East Sidewalk Waypoints
        graph.add_node("N_EAST_MID", 37.776450, -122.419200, "East Sidewalk Midpoint")
        
        # Route 2: West Sidewalk Waypoints (Parallel sidewalk ~35m west)
        graph.add_node("N_WEST_MID", 37.776450, -122.419600, "West Sidewalk Midpoint")

        # Route 3: Cross corridor (Crossing segment)
        graph.add_node("N_CROSS_EAST", 37.776450, -122.419220, "Crosswalk East Curb")
        graph.add_node("N_CROSS_WEST", 37.776450, -122.419580, "Crosswalk West Curb")

        now_iso = datetime.now(timezone.utc).isoformat()
        stale_iso = "2026-01-01T00:00:00+00:00"

        # Segments for Corridor East (Recently surveyed)
        graph.add_segment("SEG_EAST_1", "N_ORIGIN", "N_EAST_MID", 180.0, "Main Ave East Sidewalk (South)", "right", now_iso)
        graph.add_segment("SEG_EAST_2", "N_EAST_MID", "N_DEST", 180.0, "Main Ave East Sidewalk (North)", "right", now_iso)

        # Segments for Corridor West (Partially unsurveyed and stale)
        graph.add_segment("SEG_WEST_1", "N_ORIGIN", "N_WEST_MID", 185.0, "Main Ave West Sidewalk (South)", "left", stale_iso)
        graph.add_segment("SEG_WEST_2", "N_WEST_MID", "N_DEST", 185.0, "Main Ave West Sidewalk (North)", "left", None)  # UNSURVEYED

        # Cross street segment
        graph.add_segment("SEG_CROSS_MID", "N_CROSS_WEST", "N_CROSS_EAST", 30.0, "Mid-block Signalized Crossing", "crosswalk", now_iso)

        return graph

