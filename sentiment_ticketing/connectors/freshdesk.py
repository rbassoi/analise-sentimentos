from typing import Any
from urllib.parse import urlparse

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
        self.domain = self._normalize_domain(domain)
        self.base_url = f"https://{self.domain}.freshdesk.com/api/v2"
        self.auth = (api_key, "X")
        self.timeout = timeout
        self.session = session or requests.Session()
        self._company_cache: dict[str, str] = {}

    def list_tickets(self, limit: int = 10) -> list[Ticket]:
        per_page = min(max(int(limit), 1), 100)
        tickets = self._request(
            "GET",
            "/tickets",
            params={
                "page": 1,
                "per_page": per_page,
                "order_by": "created_at",
                "order_type": "desc",
                "include": "description",
            },
        )
        return [self._ticket_from_payload(ticket) for ticket in tickets]

    def get_ticket(self, ticket_id: str | int) -> Ticket:
        ticket = self._request("GET", f"/tickets/{ticket_id}")
        conversations = self._request("GET", f"/tickets/{ticket_id}/conversations")

        comments = [
            item.get("body_text") or item.get("body") or ""
            for item in conversations
            if item.get("body_text") or item.get("body")
        ]

        return self._ticket_from_payload(ticket, fallback_id=ticket_id, comments=comments)

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

    def _normalize_domain(self, domain: str) -> str:
        value = domain.strip().lower()
        if not value:
            return value

        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = parsed.netloc or parsed.path
        host = host.strip().strip("/")

        if host.endswith(".freshdesk.com"):
            return host[: -len(".freshdesk.com")]
        return host.split("/")[0]

    def _ticket_from_payload(
        self,
        ticket: dict[str, Any],
        fallback_id: str | int | None = None,
        comments: list[str] | None = None,
    ) -> Ticket:
        ticket_id = ticket.get("id", fallback_id)
        company_id = ticket.get("company_id")
        company_name = self._get_company_name(company_id) if company_id else None
        return Ticket(
            id=str(ticket_id),
            subject=ticket.get("subject", ""),
            description=ticket.get("description_text") or ticket.get("description", ""),
            comments=comments or [],
            status=str(ticket.get("status")) if ticket.get("status") is not None else None,
            priority=str(ticket.get("priority")) if ticket.get("priority") is not None else None,
            company_id=str(company_id) if company_id is not None else None,
            company_name=company_name,
            source="freshdesk",
            raw=ticket,
        )

    def _get_company_name(self, company_id: str | int) -> str:
        cache_key = str(company_id)
        if cache_key in self._company_cache:
            return self._company_cache[cache_key]

        try:
            company = self._request("GET", f"/companies/{company_id}")
            company_name = company.get("name") or f"Empresa {company_id}"
        except requests.RequestException:
            company_name = f"Empresa {company_id}"

        self._company_cache[cache_key] = company_name
        return company_name

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
