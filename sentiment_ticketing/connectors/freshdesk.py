from typing import Any

import requests

from sentiment_ticketing.connectors.base import TicketConnector
from sentiment_ticketing.core.models import SentimentResult, Ticket


class FreshdeskConnector(TicketConnector):
    def __init__(
        self,
        domain: str,
        api_key: str,
        timeout: int = 15,
        session: requests.Session | None = None,
    ):
        self.base_url = f"https://{domain}.freshdesk.com/api/v2"
        self.auth = (api_key, "X")
        self.timeout = timeout
        self.session = session or requests.Session()

    def get_ticket(self, ticket_id: str | int) -> Ticket:
        ticket = self._request("GET", f"/tickets/{ticket_id}")
        conversations = self._request("GET", f"/tickets/{ticket_id}/conversations")

        comments = [
            item.get("body_text") or item.get("body") or ""
            for item in conversations
            if item.get("body_text") or item.get("body")
        ]

        return Ticket(
            id=str(ticket.get("id", ticket_id)),
            subject=ticket.get("subject", ""),
            description=ticket.get("description_text") or ticket.get("description", ""),
            comments=comments,
            status=str(ticket.get("status")) if ticket.get("status") is not None else None,
            priority=str(ticket.get("priority")) if ticket.get("priority") is not None else None,
            source="freshdesk",
            raw=ticket,
        )

    def update_ticket_sentiment(
        self,
        ticket_id: str | int,
        sentiment: SentimentResult,
    ) -> None:
        payload = {
            "custom_fields": {
                "sentiment_score": sentiment.score,
                "sentiment_label": sentiment.label,
            }
        }
        self._request("PUT", f"/tickets/{ticket_id}", json=payload)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            auth=self.auth,
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
