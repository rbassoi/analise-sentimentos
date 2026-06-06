from typing import Any

import requests

from sentiment_ticketing.connectors.base import TicketConnector
from sentiment_ticketing.core.models import SentimentResult, Ticket


class GenericHttpConnector(TicketConnector):
    def __init__(
        self,
        base_url: str,
        get_ticket_path: str,
        update_ticket_path: str,
        token: str | None = None,
        text_field: str = "description",
        subject_field: str = "subject",
        timeout: int = 15,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.get_ticket_path = get_ticket_path
        self.update_ticket_path = update_ticket_path
        self.text_field = text_field
        self.subject_field = subject_field
        self.timeout = timeout
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def get_ticket(self, ticket_id: str | int) -> Ticket:
        payload = self._request("GET", self.get_ticket_path, ticket_id)
        return Ticket(
            id=str(payload.get("id", ticket_id)),
            subject=str(payload.get(self.subject_field, "")),
            description=str(payload.get(self.text_field, "")),
            source="generic_http",
            raw=payload,
        )

    def update_ticket_sentiment(
        self,
        ticket_id: str | int,
        sentiment: SentimentResult,
    ) -> None:
        payload = {
            "sentiment": {
                "score": sentiment.score,
                "label": sentiment.label,
                "positive_matches": sentiment.positive_matches,
                "negative_matches": sentiment.negative_matches,
            }
        }
        self._request("PATCH", self.update_ticket_path, ticket_id, json=payload)

    def _request(
        self,
        method: str,
        path_template: str,
        ticket_id: str | int,
        **kwargs: Any,
    ) -> Any:
        path = path_template.format(ticket_id=ticket_id, id=ticket_id)
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=self.headers,
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response.json() if response.content else {}
