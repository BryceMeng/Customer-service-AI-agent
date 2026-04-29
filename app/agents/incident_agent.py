"""Incident classification helpers."""

import logging

from app.schemas.case import Incident

logger = logging.getLogger(__name__)


def has_active_incident(incidents: list[Incident]) -> bool:
    active = any(incident.status in {"open", "investigating"} for incident in incidents)
    logger.info("AGENT:incident  total=%d  active=%s", len(incidents), active)
    return active
