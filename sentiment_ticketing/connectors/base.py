from abc import ABC, abstractmethod

from sentiment_ticketing.core.models import SentimentResult, Ticket


class TicketConnector(ABC):
    @abstractmethod
    def get_ticket(self, ticket_id: str | int) -> Ticket:
        raise NotImplementedError

    @abstractmethod
    def update_ticket_sentiment(
        self,
        ticket_id: str | int,
        sentiment: SentimentResult,
    ) -> None:
        raise NotImplementedError
