"""Mock observability tools."""

from app.schemas.case import BackendState


class IncidentTools:
    """Read incident/deployment evidence from local case state."""

    def __init__(self, state: BackendState) -> None:
        self._state = state

    def search_incidents(self, service: str, window: str = "24h") -> dict:
        incidents = [
            incident for incident in self._state.incidents if incident.service == service
        ]
        return {
            "window": window,
            "incidents": [incident.model_dump() for incident in incidents],
        }

    def get_recent_deployments(self, service: str) -> dict:
        deployments = [
            deployment for deployment in self._state.deployments if deployment.service == service
        ]
        return {"deployments": [deployment.model_dump() for deployment in deployments]}

    def query_metrics(self, metric_name: str, window: str = "1h") -> dict:
        incidents = [i for i in self._state.incidents if i.status in {"open", "investigating"}]
        error_rate = 0.45 if incidents else 0.01
        return {
            "metric_name": metric_name,
            "window": window,
            "data_points": [
                {"offset_minutes": 0, "value": error_rate},
                {"offset_minutes": 15, "value": error_rate * 0.9},
                {"offset_minutes": 30, "value": error_rate * 0.7},
                {"offset_minutes": 45, "value": error_rate * 0.5},
                {"offset_minutes": 60, "value": 0.01},
            ],
            "unit": "ratio",
        }

    def query_logs(self, service: str, filters: dict | None = None) -> dict:
        incidents = [i for i in self._state.incidents if i.service == service]
        logs = []
        for incident in incidents:
            logs.append({
                "timestamp": "2026-04-23T10:00:00Z",
                "level": "ERROR",
                "service": service,
                "message": incident.summary,
                "incident_id": incident.incident_id,
            })
        if not logs:
            logs.append({
                "timestamp": "2026-04-23T10:00:00Z",
                "level": "INFO",
                "service": service,
                "message": f"No error logs found for service {service!r} in current state.",
            })
        return {"service": service, "filters": filters or {}, "logs": logs}

