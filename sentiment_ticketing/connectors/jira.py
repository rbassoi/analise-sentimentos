from typing import Any

import requests

from sentiment_ticketing.connectors.base import TicketConnector
from sentiment_ticketing.core.models import SentimentResult, Ticket


class JiraServiceManagementConnector(TicketConnector):
    def __init__(
        self,
        site_url: str,
        email: str,
        api_token: str,
        sentiment_label_field: str | None = None,
        sentiment_score_field: str | None = None,
        timeout: int = 15,
        session: requests.Session | None = None,
    ):
        self.base_url = site_url.rstrip("/")
        self.auth = (email, api_token)
        self.sentiment_label_field = sentiment_label_field
        self.sentiment_score_field = sentiment_score_field
        self.timeout = timeout
        self.session = session or requests.Session()

    def get_ticket(self, ticket_id: str | int) -> Ticket:
        payload = self._request(
            "GET",
            f"/rest/api/3/issue/{ticket_id}",
            params={"fields": "summary,description,status,priority,comment"},
        )
        fields = payload.get("fields", {})
        comments = [
            self._extract_adf_text(comment.get("body"))
            for comment in fields.get("comment", {}).get("comments", [])
            if comment.get("body")
        ]

        return Ticket(
            id=str(payload.get("key", ticket_id)),
            subject=str(fields.get("summary", "")),
            description=self._extract_adf_text(fields.get("description")),
            comments=comments,
            status=self._nested_name(fields.get("status")),
            priority=self._nested_name(fields.get("priority")),
            source="jira",
            raw=payload,
        )

    def update_ticket_sentiment(
        self,
        ticket_id: str | int,
        sentiment: SentimentResult,
    ) -> None:
        fields: dict[str, Any] = {}
        if self.sentiment_label_field:
            fields[self.sentiment_label_field] = sentiment.label
        if self.sentiment_score_field:
            fields[self.sentiment_score_field] = sentiment.score
        if not fields:
            return
        self._request("PUT", f"/rest/api/3/issue/{ticket_id}", json={"fields": fields})

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            auth=self.auth,
            timeout=self.timeout,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            **kwargs,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def _nested_name(self, value: dict[str, Any] | None) -> str | None:
        if not value:
            return None
        name = value.get("name")
        return str(name) if name else None

    def _extract_adf_text(self, node: Any) -> str:
        if not node:
            return ""
        if isinstance(node, str):
            return node
        if isinstance(node, list):
            return " ".join(self._extract_adf_text(item) for item in node).strip()
        if isinstance(node, dict):
            parts = []
            if node.get("text"):
                parts.append(str(node["text"]))
            if node.get("content"):
                parts.append(self._extract_adf_text(node["content"]))
            return " ".join(part for part in parts if part).strip()
        return ""
