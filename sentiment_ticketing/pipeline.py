from sentiment_ticketing.connectors.base import TicketConnector
from sentiment_ticketing.core.models import SentimentResult
from sentiment_ticketing.core.sentiment_analyzer import KeywordSentimentAnalyzer


class TicketSentimentPipeline:
    def __init__(
        self,
        connector: TicketConnector,
        analyzer: KeywordSentimentAnalyzer | None = None,
    ):
        self.connector = connector
        self.analyzer = analyzer or KeywordSentimentAnalyzer()

    def analyze_and_update(self, ticket_id: str | int) -> SentimentResult:
        ticket = self.connector.get_ticket(ticket_id)
        sentiment = self.analyzer.analyze(ticket.analysis_text)
        self.connector.update_ticket_sentiment(ticket.id, sentiment)
        return sentiment
